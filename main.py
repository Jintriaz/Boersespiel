# 📦 Benötigte Pakete: streamlit, yfinance, pandas, etc.
import streamlit as st
import yfinance as yf
import numpy as np
import requests
import pandas as pd
import json
import os
from datetime import datetime

# 📁 Benutzerdatei laden
USERS_FILE = "users.json"
TICKER_FILE = "tickers.csv"
NEWS_API_KEY = "0e4fc2d055ec43909fa120050d458793"

# 💾 Beispielhafte Dividendenrenditen
DIVIDEND_YIELDS = {
    "AAPL": 0.005,
    "MSFT": 0.009,
    "KO": 0.03,
    "PEP": 0.025
}

# 📃 Aktienliste laden
TICKER_DATA = pd.read_csv(TICKER_FILE)

# 🔐 Session State initialisieren
if "user" not in st.session_state:
    st.session_state.user = None

# 🔄 Hilfsfunktionen
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def get_price(symbol):
    try:
        ticker = yf.Ticker(symbol)
        return ticker.history(period="1d")["Close"].iloc[-1]
    except:
        return None

def get_stock_news(symbol, count=5):
    try:
        ticker = yf.Ticker(symbol)
        news_items = ticker.news[:count]
        return news_items
    except:
        return []

def get_external_news(symbol, query=None):
    search_query = query if query else symbol
    url = f"https://newsapi.org/v2/everything?q={search_query}&sortBy=publishedAt&language=de&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("articles", [])
    return []

def get_risk_data(symbol, period="1y"):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)

        if len(data) < 2:
            return None

        # Tägliche Renditen berechnen
        data['daily_return'] = data['Close'].pct_change().dropna()

        # 1. Volatilität (annualisiert)
        volatility = data['daily_return'].std() * (252 ** 0.5)

        # 2. Beta (vs S&P 500)
        market_data = yf.Ticker("^GSPC").history(period=period)['Close'].pct_change().dropna()
        beta = data['daily_return'].cov(market_data) / market_data.var()

        # 3. Value at Risk (95% Konfidenzintervall)
        var_95 = -np.percentile(data['daily_return'].dropna(), 5)

        # 4. Sharpe Ratio (angenommene risikofreie Rate von 0%)
        sharpe_ratio = data['daily_return'].mean() / data['daily_return'].std() * np.sqrt(252)

        # 5. Maximum Drawdown
        data['cum_return'] = (1 + data['daily_return']).cumprod()
        data['rolling_max'] = data['cum_return'].cummax()
        data['drawdown'] = data['cum_return'] / data['rolling_max'] - 1
        max_drawdown = data['drawdown'].min()

        return {
            'volatility': volatility,
            'beta': beta,
            'var_95': var_95,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'price_history': data['Close'],
            'drawdown_history': data['drawdown']
        }

    except Exception as e:
        st.error(f"Fehler bei der Risikoanalyse: {str(e)}")
        return None


# 🔹 Login & Registrierung
users = load_users()

st.title("📊 Planspiel Börse")
if not st.session_state.user:
    choice = st.radio("Login oder Registrieren", ["Login", "Registrieren"])
    username = st.text_input("Benutzername")
    password = st.text_input("Passwort", type="password")

    if choice == "Registrieren":
        if st.button("Registrieren"):
            if username in users:
                st.warning("Benutzername existiert bereits.")
            else:
                users[username] = {
                    "password": password,
                    "cash": 10000.0,
                    "portfolio": {},
                    "history": []
                }
                save_users(users)
                st.success("Registrierung erfolgreich. Bitte einloggen.")

    if choice == "Login":
        if st.button("Login"):
            if username in users and users[username]["password"] == password:
                st.session_state.user = username
                st.success("Login erfolgreich.")
                st.rerun()
            else:
                st.error("Falsche Zugangsdaten.")
    st.stop()

# 🔹 Hauptmenü
user = users[st.session_state.user]
page = st.sidebar.selectbox("📚 Menü", [
    "📈 Dashboard",
    "📅 Kaufen",
    "📄 Verkaufen",
    "⚠️ Risikoanalyse",
    "📜 Historie",
    "📈 Kurs + News",
    "💸 Dividenden",
    "📉 Shorten",
    "🏆 Rangliste"
])

# 🚪 Logout-Button in Sidebar
if st.sidebar.button("🚪 Logout"):
    st.session_state.user = None
    st.session_state.clear()
    st.success("Du hast dich erfolgreich ausgeloggt.")
    st.rerun()

# 📊 Dashboard
if page == "📈 Dashboard":
    st.subheader("💼 Portfolio")
    total = user["cash"]
    for sym, qty in user["portfolio"].items():
        price = get_price(sym)
        if price:
            total += price * qty
            st.write(f"{sym}: {qty} Aktien @ {price:.2f} € = {price * qty:.2f} €")
    st.write(f"**Bargeld:** {user['cash']:.2f} €")
    st.write(f"**Gesamtwert:** {total:.2f} €")

# 📅 Kaufen
elif page == "📅 Kaufen":
    st.subheader("📅 Aktie kaufen")
    selection = st.selectbox("Aktie auswählen", TICKER_DATA["symbol"] + " – " + TICKER_DATA["name"])
    symbol = selection.split(" – ")[0]

    # Aktuellen Kurs der gewählten Aktie abrufen
    price = get_price(symbol)

    if price:
        st.write(f"**Aktueller Kurs für {symbol}: {price:.2f} €**")
    else:
        st.warning(f"Der Kurs für {symbol} konnte nicht abgerufen werden.")

    # Menge der zu kaufenden Aktien
    quantity = st.number_input("Anzahl", 1, step=1)
    total_cost = quantity * price if price else 0

    if st.button("Kaufen"):
        if price:
            if user["cash"] >= total_cost:
                user["cash"] -= total_cost
                user["portfolio"][symbol] = user["portfolio"].get(symbol, 0) + quantity
                user["history"].append({
                    "type": "Kauf", "symbol": symbol, "quantity": quantity, "price": price,
                    "total": total_cost, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                save_users(users)
                st.success(f"Kauf von {quantity} Aktien {symbol} erfolgreich.")
            else:
                st.error("Nicht genug Bargeld.")
        else:
            st.error("Es konnte kein Kurs für die Aktie abgerufen werden.")

# 📄 Verkaufen
elif page == "📄 Verkaufen":
    st.subheader("📄 Aktie verkaufen")
    if not user["portfolio"]:
        st.info("Keine Aktien im Depot.")
    else:
        symbol = st.selectbox("Symbol", list(user["portfolio"].keys()))
        max_qty = user["portfolio"][symbol]
        quantity = st.number_input("Anzahl", 1, max_value=max_qty, step=1)
        price = get_price(symbol)
        if st.button("Verkaufen"):
            user["cash"] += quantity * price
            user["portfolio"][symbol] -= quantity
            if user["portfolio"][symbol] == 0:
                del user["portfolio"][symbol]
            user["history"].append({
                "type": "Verkauf", "symbol": symbol, "quantity": quantity, "price": price,
                "total": quantity * price, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_users(users)
            st.success("Verkauf erfolgreich.")

# ⚠️ Risikoanalyse
elif page == "⚠️ Risikoanalyse":
    st.subheader("📉 Detaillierte Risikoanalyse")
    selection = st.selectbox("Aktie auswählen", TICKER_DATA["symbol"] + " – " + TICKER_DATA["name"])
    symbol = selection.split(" – ")[0]
    risk_data = get_risk_data(symbol)
    if risk_data is None:
        st.warning("Konnte keine Risikodaten abrufen. Bitte später erneut versuchen oder ein anderes Symbol wählen.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "📈 Annualisierte Volatilität",
                f"{risk_data['volatility'] * 100:.2f}%",
            )
            st.info("Zeigt die Schwankungsbreite des Preises im Jahr.")

            st.metric(
                "🛡️ Beta (vs. Markt)",
                f"{risk_data['beta']:.2f}"
            )
            st.info("Maß für Marktabhängigkeit (Beta >1: volatiler als Markt)")

            st.metric(
                "💰 Value at Risk (95%)",
                f"{risk_data['var_95'] * 100:.2f}%"
            )
            st.info("Täglicher Verlust, den man mit 95% Wahrscheinlichkeit nicht überschreitet.")

        with col2:
            st.metric(
                "🎯 Sharpe Ratio",
                f"{risk_data['sharpe_ratio']:.2f}"
            )
            st.info("Rendite pro Risikoeinheit. Höher ist besser (>1 gut).")

            st.metric(
                "🔻 Maximaler Drawdown",
                f"{risk_data['max_drawdown'] * 100:.2f}%"
            )
            st.info("Maximaler Rückgang vom Hochpunkt zum Tiefpunkt.")

        # Visualisierungen
        st.divider()
        st.subheader("📊 Kurs- & Drawdown-Verlauf")

        vis_col1, vis_col2 = st.columns(2)

        with vis_col1:
            st.line_chart(risk_data['price_history'], use_container_width=True)

        with vis_col2:
            st.area_chart(risk_data['drawdown_history'], use_container_width=True)

# 📜 Historie
elif page == "📜 Historie":
    st.subheader("📜 Transaktionshistorie")
    hist_df = pd.DataFrame(user["history"])
    st.dataframe(hist_df[::-1])

# 📈 Kurs + News
elif page == "📈 Kurs + News":
    st.subheader("📈 Kursdaten & News")
    selection = st.selectbox("Aktie auswählen", TICKER_DATA["symbol"] + " – " + TICKER_DATA["name"])
    symbol = selection.split(" – ")[0]

    # Kursdiagramm
    data = yf.Ticker(symbol).history(period="1mo")
    st.line_chart(data["Close"])

    st.divider()
    st.subheader(f"📰 Externe News zu {symbol}")

    news = get_external_news(symbol, query=symbol + " stock")

    if news:
        for article in news[:5]:  # Begrenze auf 5 Artikel
            title = article.get("title", "Kein Titel")
            description = article.get("description", "")
            url = article.get("url", "#")
            source = article.get("source", {}).get("name", "Unbekannte Quelle")
            published_at = article.get("publishedAt", "").split("T")[0]

            st.markdown(f"""
            ### [{title}]({url})  
            **{source} – {published_at}**  
            {description}
            """)
    else:
        st.info("Keine externen Nachrichten gefunden.")

# 💸 Dividenden
elif page == "💸 Dividenden":
    st.subheader("📆 Dividenden auszahlen")
    payout_button = st.button("Jetzt Dividenden erhalten")
    if payout_button:
        payout_total = 0
        for sym, qty in user["portfolio"].items():
            if sym in DIVIDEND_YIELDS:
                price = get_price(sym)
                if price:
                    div = price * DIVIDEND_YIELDS[sym] * qty
                    payout_total += div
        if payout_total > 0:
            user["cash"] += payout_total
            save_users(users)
            st.success(f"Du hast {payout_total:.2f} € an Dividenden erhalten.")
        else:
            st.info("Keine Dividenden verfügbar.")

# 📉 Shorten
elif page == "📉 Shorten":
    st.subheader("📉 Aktie shorten")
    symbol = st.selectbox("Aktie auswählen", TICKER_DATA["symbol"] + " – " + TICKER_DATA["name"])
    quantity = st.number_input("Anzahl", 1, step=1)
    price = get_price(symbol)
    if st.button("Shorten"):
        st.success(f"{quantity} Aktien von {symbol} erfolgreich geshortet!")

elif page == "🏆 Rangliste":
    st.subheader("🏆 Rangliste")

    leaderboard_data = []

    for username, data in users.items():
        cash = data["cash"]
        portfolio_value = 0.0
        for sym, qty in data["portfolio"].items():
            price = get_price(sym)
            if price:
                portfolio_value += price * qty
        total_value = cash + portfolio_value
        leaderboard_data.append({
            "Benutzer": username,
            "Gesamtwert": total_value,
            "Bargeld": cash,
            "Depotwert": portfolio_value
        })

    leaderboard_df = pd.DataFrame(leaderboard_data)
    leaderboard_df = leaderboard_df.sort_values(by="Gesamtwert", ascending=False).reset_index(drop=True)

    # Pokale vergeben
    pokale = ["🥇", "🥈", "🥉"] + [""] * (len(leaderboard_df) - 3)
    leaderboard_df.insert(0, "Platz", [f"{pokale[i]} {i+1}" for i in range(len(leaderboard_df))])

    st.table(leaderboard_df.style.format({
        "Gesamtwert": "{:.2f} €",
        "Bargeld": "{:.2f} €",
        "Depotwert": "{:.2f} €"
    }))
