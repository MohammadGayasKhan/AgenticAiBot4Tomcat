##UI Based ChatBot Application

from chatbot import ChatBot
from Tools.EventsTracking import EventsTracking
from Tools.Weather import Weather
from Tools.LocationMe import LocateMe
from Tools.ConvertCurrency import ConvertCurrency
import streamlit as st

st.set_page_config(page_title="ChatBot Simulation", page_icon="💬", layout="centered")
currency_tool = ConvertCurrency()
weather_tool = Weather()
location_tool = LocateMe() 

chatbot = ChatBot(tools=[currency_tool, weather_tool, location_tool])
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("Simple ChatBot Simulation")
st.write("Type your message below and chat with the bot!")

if "pending_message" not in st.session_state:
    st.session_state.pending_message = ""

def send_message():
    text = st.session_state.get('pending_message', '').strip()
    if not text:
        return
    st.session_state.chat_history.append(("user", text))
    bot_response = chatbot.perform_task(text)
    st.session_state.chat_history.append(("bot", bot_response))
    st.session_state.pending_message = ""

def clear_chat():
    st.session_state.chat_history = []
    st.success("Chat history cleared!")

user_input = st.text_input("Your message:", placeholder="Type here...", key="pending_message")

st.button("Send", key="send_btn", on_click=send_message)
st.button("🧹 Clear Chat", key="clear_btn", on_click=clear_chat)

st.markdown("### Chat History")
for role, message in st.session_state.chat_history:
    if role == "user":
        st.markdown(f"🧑 **You:** {message}")
    else:
        st.markdown(f"🤖 **Bot:** {message}")





