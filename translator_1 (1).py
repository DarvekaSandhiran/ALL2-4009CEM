

# Standard library
import sqlite3
import pathlib
import os
import threading
import time

# v Install dependencies

try:
    import PySimpleGUI as sg
    from deep_translator import GoogleTranslator
    from gtts import gTTS
    from playsound import playsound
    import speech_recognition as sr
    import sounddevice as sd
    import soundfile as sf
    import ffmpeg
    from scipy.io.wavfile import write
    import pyaudio
    import wave
except ModuleNotFoundError:

    import subprocess
    import sys

    def pip_install(module):
        subprocess.check_call([sys.executable, "-m", "pip", "install", module])

    modules = [
            'PySimpleGUI',
            'deep_translator',
            'gtts',
            # 'playsound', # Special version needed for Windows. 1.2.2
            'SpeechRecognition',
            'scipy',
            'sounddevice',
            'ffmpeg-python',
            'soundFile'
            ]

    print("# One or more modules were not found! Installing modules:")
    for module in modules:
        pip_install(module)

    subprocess.check_call([sys.executable, "-m", "pip",
                          "install", "playsound==1.2.2"])

    print('\n\nDependencies installed for the next run!')
    quit()
# ^ Install dependencies


def create_db(db_filename=""):
    if not db_filename:
        return
    sql_conn = sqlite3.connect(db_filename)
    sql_cur = sql_conn.cursor()
    sql_cur.execute("""
    CREATE TABLE IF NOT EXISTS history (
        fromtext STR,
        totext STR
        );
    """)
    sql_conn.commit()
    return


def add_to_history_db(db_filename="", from_text="", to_text=""):
    if not db_filename or not from_text or not to_text:
        print("At least one of these arguments were none:")
        print("db_filename", "from_text", "to_text")
        print(db_filename, from_text, to_text)
        return
    sql_conn = sqlite3.connect(db_filename)
    sql_cur = sql_conn.cursor()
    sql_cur.execute(f"""
    INSERT INTO history VALUES(
        "{from_text}",
        "{to_text}"
    )
    """)
    sql_conn.commit()
    return


def text_to_speech(text, language=None):
    if not language:
        return
    if not text:
        return
    sound_filename = "last_listened.mp3"
    if pathlib.Path(sound_filename).exists():
        os.remove(sound_filename)

    speech = gTTS(text=text, lang=language, slow=False)
    speech.save(sound_filename)
    playsound(sound_filename)
    return

def speech_to_text(mic_file_in, language=None):
    if not language:
        return

    # Convert to text
    r = sr.Recognizer()
    audio_file = sr.AudioFile(mic_file_in)
    with audio_file as audio_source:
        r.adjust_for_ambient_noise(audio_source)
        audio_data = r.record(audio_source)

    # set up the response object
    response = {
        "success": True,
        "error": None,
        "transcription": None
    }

    # try recognizing the speech in the recording
    # if a RequestError or UnknownValueError exception is caught,
    #     update the response object accordingly
    try:
        response["transcription"] = r.recognize_google(audio_data, language=language)
    except sr.RequestError:
        # API was unreachable or unresponsive
        response["success"] = False
        response["transcription"] = "API unavailable"
    except sr.UnknownValueError:
        # speech was unintelligible
        response["transcription"] = "Unable to recognize speech"
    return response["transcription"]


def long_operation_thread(seconds, window):
    """
    A worker thread that communicates with the GUI through a queue
    This thread can block for as long as it wants and the GUI will not be affected
    :param seconds: (int) How long to sleep, the ultimate blocking call
    :param gui_queue: (queue.Queue) Queue to communicate back to GUI that task is completed
    :return:
    """
    print('recording....')
    window['-MICROPHONE-'].update("Recording")

    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels = 1, rate=44100, input=True, frames_per_buffer=1024)
    frames = []

    while (True):
        data = stream.read(1024)
        frames.append(data)

        if event == "-STOP-":
            print('Stopping....')
            break
    stream.stop_stream()
    stream.close()
    audio.terminate()

    # print(frames)

    sound_file = wave.open("myrecording.wav", "wb")
    sound_file.setnchannels(1)
    sound_file.setsampwidth(audio.get_sample_size(pyaudio.paInt16))  
    sound_file.setframerate(44100)
    sound_file.writeframes(b''.join(frames))
    sound_file.close()  

    new_fromtext = speech_to_text("myrecording.wav", language=mic_lang)

    window['-MICROPHONE-'].update("Microphone")
    window["-FROMTEXT-"].update(new_fromtext)

if __name__ == "__main__":
    db_path = "history.db"
    if not pathlib.Path(db_path).exists():
        create_db(db_path)

    sg.theme("Gray Gray Gray")  # Try to match the system theme



    lang_choices = {
            'chinese (simplified)': 'zh-CN',
            'chinese (traditional)': 'zh-TW',
            'english': 'en',
            'malay': 'ms'
    }

    tts_langcodes = {
            'english': 'en',
            'malay': 'ms',
            'chinese': 'zh-CN'
            }
    stt_langcodes = {
            'english': 'en-US',
            'malay': 'ms-MY',
            'chinese': 'zh-CN'
            }

    default_width = 25
    default_height = 1

    btn_from_lang = sg.Combo(
            list(lang_choices), default_value=list(lang_choices)[0], key="-FROMLANG-")
    btn_to_lang = sg.Combo(
            list(lang_choices), default_value=list(lang_choices)[2], key="-TOLANG-")
    btn_microphone = sg.Button("Microphone", key="-MICROPHONE-")
    btn_stop = sg.Button("Stop", key="-STOP-")

    input_from_text = sg.Multiline(
            size=(default_width, 4), key="-FROMTEXT-")
    input_to_text = sg.Multiline(
            size=(default_width, 4), key="-TOTEXT-")

    btn_listen_from_text = sg.Button("Listen", key="-LISTENFROMLANG-")
    btn_listen_to_text = sg.Button("Listen", key="-LISTENTOLANG-")
    btn_translate = sg.Button("Translate", key="-TRANSLATE-")

    layout = [
        [btn_from_lang, sg.Push(), btn_to_lang],
        [btn_microphone, btn_stop],
        [input_from_text, input_to_text],
        [btn_listen_from_text, sg.Push(), btn_listen_to_text],
        [btn_translate],
    ]

    window = sg.Window("Translator", layout, resizable=True, scaling=3, element_padding=30)

    # Start loop to read user interactions
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == "Exit":
            window.close()
            break

        if event == "-TRANSLATE-":
            new_totext = GoogleTranslator(source=values['-FROMLANG-'], target=values['-TOLANG-']) \
                    .translate(values['-FROMTEXT-'])

            window["-TOTEXT-"].update(new_totext)

            add_to_history_db(db_path, values['-FROMTEXT-'], new_totext)

        if event == "-LISTENFROMLANG-":
            text_to_hear = values['-FROMTEXT-']
            language_to_hear = tts_langcodes[ \
                    values['-FROMLANG-'].split()[0] \
                    ]
            text_to_speech(text_to_hear, language=language_to_hear)

        if event == "-LISTENTOLANG-":
            text_to_hear = values['-TOTEXT-']
            language_to_hear = tts_langcodes[ \
                    values['-TOLANG-'].split()[0] \
                    ]
            text_to_speech(text_to_hear, language=language_to_hear)

        if event == "-MICROPHONE-":
            mic_lang = stt_langcodes[ \
                    values['-FROMLANG-'].split()[0] \
                    ]
            threading.Thread(target=long_operation_thread, args=(500, window,), daemon=True).start()
            # new_fromtext = speech_to_text("myrecording.wav", language=mic_lang)

            window['-MICROPHONE-'].update("Microphone")
            # window["-FROMTEXT-"].update(new_fromtext)

        print("Values read: ", values)
        print("Event read: ", event)

    window.close()
