import datetime
import json
import math
from decimal import Decimal
import time
import os
import re
from difflib import SequenceMatcher
import requests
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render
from ffmpy import FFmpeg
from django.core.exceptions import ObjectDoesNotExist
import wordcounter


# Create your views here.
def home(request):
    return render(request, 'uploads/home.html')

'''The upload function takes in a video or audio file along with the summarisation percentage. This is all sent to the 
the video_clip function which is the summarisation function'''
def simple_upload(request):
    try:
        if request.method == 'POST' and request.FILES['myfile']:
            myfile = request.FILES['myfile']
            mypercent = request.POST['mypercent']
            topsent = request.POST['topsent']
            request.session['topsent'] = topsent
            request.session['mypercent'] = mypercent
            print("PERCENTAGE CHOOSEN " + mypercent)
            print("Top CHOOSEN " + topsent)
            fs = FileSystemStorage()
            filename = fs.save(myfile.name, myfile)
            uploaded_file_path = fs.url(filename)
            time_break = []
            time_break.append("Upload File " + time.ctime())
            request.session['time_break'] = time_break
            if uploaded_file_path.endswith('.mp4'):
                file_extentionV = '.mp4'
                request.session['file_extentionV'] = file_extentionV
                request.session['uploaded_file_path'] = uploaded_file_path
                return render(request, 'uploads/home.html', {
                    'file_extentionV': file_extentionV, 'uploaded_file_path': uploaded_file_path})
            else:
                file_extentionA = '.flac'
                request.session['uploaded_file_path'] = uploaded_file_path
                return render(request, 'uploads/home.html', {
                    'file_extentionA': file_extentionA, 'uploaded_file_path': uploaded_file_path})


    except Exception:
        return render(request, 'uploads/home.html')

    return render(request, 'uploads/home.html')


def video_clip(request):

    '''This is the Video Split Function'''
    time_break = request.session.get('time_break')
    time_break.append("Start Summarisation " + time.ctime())
    short_path = request.session.get('uploaded_file_path')
    cut_path = str(short_path[1:])
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MEDIA_ROOT = os.path.join(BASE_DIR, '').replace('\\','/')
    print(BASE_DIR)
    full_path = (MEDIA_ROOT[2:]+cut_path).replace('%20',' ')
    output_path = (MEDIA_ROOT+cut_path)[:-4] + '.flac'

    # print("FULL path HERE:" + full_path)
    # print("OUTPUT path HERE:" + output_path)

    try:
        if full_path.endswith('.flac'):
            output_path = (MEDIA_ROOT + cut_path)[:-5] + '.flac'
            full_path = output_path

        else:
            ve = FFmpeg(
                inputs={full_path: None},
                outputs={output_path: ['-y', '-f', 'flac', '-ab', '192000', '-vn']}
            )
            # print(ve.cmd)
            ve.run()
            time_break.append("Convert V to A "+time.ctime())

            # print("OUTPUT path HERE:" + output_path)
            # print("FULL path HERE:" + full_path)
    except Exception:
        return render(request, 'uploads/home.html')

    '''This is the Transcription Function'''
    tr = open("output.json", "w+")
    audio_path = open(output_path, "rb")
    response = requests.post("https://stream.watsonplatform.net/speech-to-text/api/v1/recognize?timestamps=true",
                             auth=("f7c2c504-fa84-4134-bf08-916409f4d53a", "3STmtCX6PaUM"),
                             headers={"Content-Type": "audio/flac"},
                             data=audio_path
                             )
    tr.write(response.text)
    time_break.append("Transcription " + time.ctime())
    # print("\nResponse is\n" + response.text + "\nAudio_path=" + str(output_path))
    tr.close()

    '''This is the Extract Text Function'''
    data = json.load(open('output.json'))
    et = open("sentences.txt", "w+")
    for alt_result in data["results"]:
        for transcription in alt_result["alternatives"]:
            # By substituting fullstops with a space it prevents unexpected end of sentence when summarizing
            nstr = re.sub(r'[.]', r'', transcription["transcript"])
            et.write(nstr + '.\n')
    time_break.append("Text Extract " + time.ctime())
    et.close()

    sample = open('sentences.txt').read()
    stop_words = set(open('resources/stopwords.txt').read().split())

    summry = open("summary.txt", "w+")

    caps = "([A-Z])"
    prefixes = "(Mr|St|Mrs|Ms|Dr)[.]"
    suffixes = "(Inc|Ltd|Jr|Sr|Co)"
    starters = "(Mr|Mrs|Ms|Dr|He\s|She\s|It\s|They\s|Their\s|Our\s|We\s|But\s|However\s|That\s|This\s|Wherever)"
    acronyms = "([A-Z][.][A-Z][.](?:[A-Z][.])?)"
    websites = "[.](com|net|org|io|gov)"

    def get_sentences(text):
        text = " " + text + "  "
        text = text.replace("\n", " ")
        text = re.sub(prefixes, "\\1<prd>", text)
        text = re.sub(websites, "<prd>\\1", text)
        if "Ph.D" in text: text = text.replace("Ph.D.", "Ph<prd>D<prd>")
        text = re.sub("\s" + caps + "[.] ", " \\1<prd> ", text)
        text = re.sub(acronyms + " " + starters, "\\1<stop> \\2", text)
        text = re.sub(caps + "[.]" + caps + "[.]" + caps + "[.]", "\\1<prd>\\2<prd>\\3<prd>", text)
        text = re.sub(caps + "[.]" + caps + "[.]", "\\1<prd>\\2<prd>", text)
        text = re.sub(" " + suffixes + "[.] " + starters, " \\1<stop> \\2", text)
        text = re.sub(" " + suffixes + "[.]", " \\1<prd>", text)
        text = re.sub(" " + caps + "[.]", " \\1<prd>", text)
        if "\"" in text: text = text.replace(".\"", "\".")
        if "!" in text: text = text.replace("!\"", "\"!")
        if "?" in text: text = text.replace("?\"", "\"?")
        text = text.replace(".", ".<stop>")
        text = text.replace("?", "?<stop>")
        text = text.replace("!", "!<stop>")
        text = text.replace("<prd>", ".")
        sentences = text.split("<stop>")
        sentences = sentences[:-1]
        sentences = [s.strip() for s in sentences]
        return sentences
    ''' sentences, P. (2018). Python split text on sentences. [online] Stackoverflow.com. Available at: https://stackoverflow.com/questions/4576077/python-split-text-on-sentences?lq=1 [Accessed 22 Mar. 2018]. '''

    def get_score(sentence, word_scores):
        score = 0
        words = sentence.split()
        for word in words:
            if word not in stop_words:
                score += word_scores[word]
        return score

    word_scores = wordcounter.word_frequency(sample, stop_words)
    sentences = get_sentences(sample)
    scores = {}
    for indx, sentence in enumerate(sentences):
        scores[sentence] = get_score(sentence, word_scores)

    sorted_scores = list(scores.values())
    sorted_scores.sort()
    ''' summarisation percentage '''
    short_percent = "0.5"
    full_text = []
    mypercent = request.session.get('mypercent')
    topsent = request.session.get('topsent')

    if mypercent == "" and topsent == "":
        short_percent = "0.5"
        n = int(round(-1 * (float(short_percent)) * sorted_scores.__len__() + 0.5))
        threshold = sorted_scores[n - 2]

        for counter, sentence in enumerate(sentences):
            full_text.append(sentence)
            if scores[sentence] > threshold:
                summry.write(sentence + '\n')
    if topsent:
        if float(topsent) < len(sentences):
            short_percent = float(str(float(topsent) / (len(sentences))))
            n = int(round(-1 * (float(short_percent)) * sorted_scores.__len__() + 0.5))
            threshold = sorted_scores[n - 2]

            for counter, sentence in enumerate(sentences):
                full_text.append(sentence)
                if scores[sentence] > threshold:
                    summry.write(sentence + '\n')
        else:
            short_percent = str((len(sentences) / (len(sentences))) - 0.01)
            n = int(round(-1 * (float(short_percent)) * sorted_scores.__len__() + 0.5))
            threshold = sorted_scores[n - 1]

            for counter, sentence in enumerate(sentences):
                full_text.append(sentence)
                if scores[sentence] > threshold:
                    summry.write(sentence + '\n')
    elif mypercent:
        if float(mypercent) >= 100:
            short_percent = '0.99'
            n = int(round(-1 * (float(short_percent)) * sorted_scores.__len__() + 0.5))
            threshold = sorted_scores[n - 1]

            for counter, sentence in enumerate(sentences):
                full_text.append(sentence)
                if scores[sentence] > threshold:
                    summry.write(sentence + '\n')
        else:
            short_percent = mypercent
            n = int(round(-1 * (float(short_percent)) * sorted_scores.__len__() + 0.5))
            threshold = sorted_scores[n - 2]

            for counter, sentence in enumerate(sentences):
                full_text.append(sentence)
                if scores[sentence] > threshold:
                    summry.write(sentence + '\n')

    time_break.append("Summarisation " + time.ctime())
    summry.close()
    summryText = open("summary.txt", "r")

    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio()
    the_final_mp4 = ''
    timegroup = []
    timecrop = []
    concat_list = []
    all_lines = []
    count = 0
    similar_lines = []
    for c, s in enumerate(summryText):

        all_lines.append("<p style='text-transform:capitalize; padding: 0 0 0 1em;'>" + s + "</p>")
        for alt_result in data['results']:
            # print(alt_result)
            for t, transcription in enumerate(alt_result["alternatives"]):
                # print(similar(s, transcription["transcript"]))
                if c < 1:
                    similar_lines.append("<p style='text-transform:capitalize;'>" + transcription["transcript"] + '.</p>')
                for cl, l in enumerate(similar_lines):
                    l = (l[39:-4])
                    if similar(s, l) >= 0.95:
                        similar_lines[cl] = ("<p style='text-transform:capitalize;'><mark><font color='green'>" + s + "</font></mark></p>")

                if similar(s, transcription["transcript"]) >= 0.95:
                    timegroup = transcription["timestamps"]
                    startwords = timegroup[0]
                    endwords = timegroup[-1]
                    starttimes = math.trunc((startwords[1:])[0])
                    endtimes = math.ceil((endwords[1:])[1])
                    addtimes = endtimes - starttimes
                    startHour = str(datetime.timedelta(seconds=starttimes))
                    endHour = str(datetime.timedelta(seconds=endtimes))
                    addHour = str(datetime.timedelta(seconds=addtimes))
                    count = count + 1

                    # Split the video using the timestamps
                    ff = FFmpeg(
                        inputs={full_path: None},
                        outputs={'cut/part'+str(count)+'.ts': ['-y', '-ss', startHour, '-t', addHour, '-async', '1', '-strict', '-2']}
                    )
                    ff.run()
                    concat = 'concat:cut/part' + str(count) + '.ts|'
                    concat_list.append(concat)
    time_break.append("Find Time stamps & Split " + time.ctime())
    # Merge all cut parts of video together
    shortnote_ts = os.path.join(BASE_DIR, '').replace('\\', '/') + "media/output.ts"
    fm = FFmpeg(
        inputs={"".join(concat_list): None},
        outputs={shortnote_ts: ['-y', '-codec', 'copy']}
    )
    fm.run()
    time_break.append("Concat Videos " + time.ctime())

    shortnote_mp4 = shortnote_ts[:-3] + ".mp4"
    vt = FFmpeg(
        inputs={shortnote_ts: None},
        outputs={shortnote_mp4: ['-y', '-c:v', 'libx264', '-preset', 'medium', '-crf', '0']}
    )
    vt.run()
    time_break.append("Convert ts to MP4 " + time.ctime())
    cut_len = len(" /media/output.ts")
    shortnote_mp4 = shortnote_mp4[-cut_len:]
    the_final_mp4 = shortnote_mp4

    all_lines = "\n".join(all_lines)
    full_text = "\n".join(full_text)
    similar_lines = "\n".join(similar_lines)
    print(time_break)
    demo_text = open("demotext.txt", "w+")
    demo_text.write(full_text + '\n\n' + similar_lines)
    return render(request, 'uploads/summary.html', {'uploaded_file_path': short_path, 'audio_path': output_path, 'the_final_mp4': the_final_mp4, 'all_lines': all_lines, "full_text": full_text, "similar_lines": similar_lines})
