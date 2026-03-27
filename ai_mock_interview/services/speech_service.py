import speech_recognition as sr
import os

def speech_to_text(file_path):
    recognizer = sr.Recognizer()

    try:
        with sr.AudioFile(file_path) as source:
            audio = recognizer.record(source)

        text = recognizer.recognize_google(audio)

        return text

    except sr.UnknownValueError:
        return "SPEECH_NOT_DETECTED"

    except sr.RequestError as e:
        return f"AUDIO_ERROR: {str(e)}"