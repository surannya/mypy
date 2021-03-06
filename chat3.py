from chatterbot import ChatBot
from chatterbot.trainers import ListTrainer

chatbot = ChatBot(
    "FirstDemo",
    storage_adapter="chatterbot.storage.SQLStorageAdapter",
    logic_adapters=[
        "chatterbot.logic.MathematicalEvaluation",
        "chatterbot.logic.BestMatch",
        "chatterbot.logic.TimeLogicAdapter",
    ],
    input_adapter="chatterbot.input.TerminalAdapter",
    output_adapter="chatterbot.output.TerminalAdapter",
    database="../database.db"
)

chatbot.set_trainer(ListTrainer)
chatbot.train(["Hi There!",
               "Hai",
               "Hello",
               "How are you",
               "I am good",
               "It is good to hear from you",
               "Thank you",
               "You are welcome",
               "Bye",
               "OK"])

print("Type something to begin...")

while True:
    try:
        bot_input = chatbot.get_response(None)
    except (KeyboardInterrupt, EOFError, SystemExit):
        break
