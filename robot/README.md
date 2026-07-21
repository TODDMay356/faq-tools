# WeChat API Support Bot

This project implements a WeChat bot designed to act as a technical support agent for cross-border payment APIs. The bot monitors WeChat groups for mentions, extracts queries, interfaces with an internal API to fetch relevant information, and automatically responds in the WeChat group.

## 1. Solution Overview

The bot utilizes the `wxpy` library for WeChat integration. Its modular architecture consists of a WeChat Listener, Message Parser, API Client, Response Formatter, and WeChat Sender. This design ensures extensibility, maintainability, and clear separation of concerns.

## 2. Technical Stack

*   **Python**: 3.9+
*   **WeChat Integration**: `wxpy` (built on `itchat`)
*   **HTTP Requests**: `requests`
*   **Configuration Management**: `configparser` or `python-dotenv`
*   **Logging**: Python's built-in `logging` module

## 3. Project Structure

```
robot/
├── config.py             # Configuration loading
├── api_client.py         # Handles communication with the internal payment API
├── message_parser.py     # Parses WeChat messages to extract queries
├── response_formatter.py # Formats API responses for WeChat
├── wechat_bot.py         # Main bot logic, WeChat listening and sending
├── main.py               # Entry point for the application
└── README.md             # This file
```

## 4. Setup and Installation

### 4.1. Prerequisites

*   Python 3.9+
*   A WeChat account that can be logged into via QR code scan (personal account).

### 4.2. Create a Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

### 4.3. Install Dependencies

```bash
pip install -r requirements.txt
```

(Note: You will need to create `requirements.txt` with `wxpy`, `requests`, `python-dotenv`)

### 4.4. Configuration

Create a `.env` file in the `robot/` directory with the following content:

```
BOT_NAME=YourBotName  # Replace with the actual WeChat name of your bot
API_BASE_URL=http://localhost:8000/api/v1  # Replace with your internal API base URL
API_KEY=your_api_key  # Replace with your API key if required
```

## 5. Usage

### 5.1. Starting the Bot

Navigate to the `robot/` directory and run:

```bash
python main.py
```

Upon first run, a QR code will be displayed in the terminal. Scan it with your WeChat mobile app to log in the bot.

### 5.2. Interacting with the Bot

Once the bot is running and logged in:

1.  **Join WeChat Groups**: Ensure the bot's WeChat account is a member of the relevant WeChat groups.
2.  **Mention the Bot**: In any group where the bot is a member, mention the bot by its WeChat name (e.g., `@YourBotName`) followed by your query.

    Example:
    `@YourBotName query payment status for order XYZ123`

3.  **Receive Response**: The bot will process your query, call the internal API, and respond in the group with the relevant information.

## 6. Extensibility

*   **Adding New API Endpoints**: Modify `api_client.py` to include new methods for calling different API endpoints.
*   **Enhancing Message Parsing**: Update `message_parser.py` to support more complex query structures or command recognition.
*   **Customizing Responses**: Adjust `response_formatter.py` to tailor the bot's replies for various scenarios.
*   **Advanced Features**: Implement features like persistent sessions, natural language understanding (NLU) integration, or more sophisticated error handling.

## 7. Troubleshooting

*   **QR Code Not Appearing**: Ensure your terminal supports displaying images or check the log for a URL to the QR code.
*   **Bot Not Responding**: Verify that `BOT_NAME` in `.env` is correct and that the bot is properly logged in.
*   **API Errors**: Check `api_client.py` and the internal API logs for issues.
*   **WeChat Account Blocked**: Frequent or automated interactions might lead to temporary or permanent blocking by WeChat. Use the bot responsibly.

## 8. Development Notes

*   `wxpy` relies on the web WeChat client, which may have limitations or be unstable at times. Consider `itchat` for more granular control if `wxpy` proves insufficient.
*   Always keep your WeChat account secure. Be mindful of the data you expose through the bot.

---

**Disclaimer**: WeChat's terms of service may restrict automated interactions. Use this bot responsibly and be aware of potential limitations or account restrictions.
