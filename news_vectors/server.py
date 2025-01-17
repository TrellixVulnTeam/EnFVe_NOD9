from subprocess import Popen, PIPE
from flask import Flask, Response, escape, request, render_template
import requests
import json
import tensorflow_hub as hub
from annoy import AnnoyIndex
import subprocess
import redis

print('getting USE model...')
embed = hub.load('https://tfhub.dev/google/universal-sentence-encoder-large/5')
print('fetched model.')


r = redis.Redis(
    host='127.0.0.1',
    port=6379)

D=512
NUM_TREES=10
ann = AnnoyIndex(D, metric='angular')
ann.load('article_100.index')



app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def hello():

    query = request.json['claim']
    query_embedding = embed([query])
    nns = ann.get_nns_by_vector(query_embedding[0], 10)
    results = []
    for n in nns:
        result = json.loads(r.get(str(n)))
        results.append(result)

    return Response(
                    json.dumps({'news_article_evidences': results}),
                    mimetype='application/json',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Access-Control-Allow-Origin': '*'
                    }
                )


app.run(
    host='0.0.0.0',
    port=15000,
    debug=False,
    threaded=True
)

# -*- coding: utf-8 -*-
"""
Data from https://aminer.org/influencelocality 
Extract network and diffusion cascades from Weibo
"""

import os
import time
import tarfile
from urllib.request import urlretrieve


def split_train_and_test(cascades_file):
    """
    # Keeps the ids of the users that are actively retweeting
    # Train time:(2011.10.29 -2012.9.28) and test time (2012.9.28 -2012.10.29)
    """
    f = open(cascades_file)
    ids = set()
    train_cascades = []
    test_cascades = []
    counter = 0

    for line in f:

        date = line.split(" ")[1].split("-")
        original_user_id = line.split(" ")[2]

        retweets = f.next().replace(" \n", "").split(" ")
        # ----- keep only the cascades and the nodes that are active in train (2011.10.29 -2012.9.28) and test (2012.9.28 -2012.10.29)

        retweet_ids = ""

        # ------- last month at test
        if int(date[0]) == 2012 and (
                (int(date[1]) >= 9 and int(date[2]) >= 28) or (int(date[1]) == 10 and int(date[2]) <= 29)):
            ids.add(original_user_id)

            cascade = ""
            for i in range(0, len(retweets) - 1, 2):
                ids.add(retweets[i])
                retweet_ids = retweet_ids + " " + retweets[i]
                cascade = cascade + ";" + retweets[i] + " " + retweets[i + 1]

            # ------- For each cascade keep also the original user and the relative day of recording (1-32)
            date = str(int(date[2]) + 3)
            op = line.split(" ")
            op = op[2] + " " + op[1]
            test_cascades.append(date + ";" + op + cascade)

        # ------ The rest are used for training
        elif (int(date[0]) == 2012 and int(date[1]) < 9 and int(date[2]) < 28) or (
                int(date[0]) == 2011 and int(date[1]) >= 10 and int(date[2]) >= 29):

            ids.add(original_user_id)
            cascade = ""
            for i in range(0, len(retweets) - 1, 2):
                ids.add(retweets[i])
                retweet_ids = retweet_ids + " " + retweets[i]
                cascade = cascade + ";" + retweets[i] + " " + retweets[i + 1]
            if (int(date[1]) == 9):
                date = str(int(date[2]) - 27)
            else:
                date = str(int(date[2]) + 3)
            op = line.split(" ")
            op = op[2] + " " + op[1]
            train_cascades.append(date + ";" + op + cascade)

        counter += 1
        if (counter % 10000 == 0):
            print("------------" + str(counter))
    f.close()

    return train_cascades, test_cascades, ids


def download():
    file_tmp = urlretreive("https://www.dropbox.com/s/r0kdgeh8eggqgd3/retweetWithoutContent.rar", filename=None)[0]
    tar = tarfile.open(fileobj=file_tmp)
    tar.extractall("total.csv")

    file_tmp = urlretreive("https://www.dropbox.com/s/r0kdgeh8eggqgd3/graph_170w_1month.rar", filename=None)[0]
    tar = tarfile.open(fileobj=file_tmp)
    tar.extractall("graph_170w_1month.txt")


def weibo_preprocessing(path):
    os.chdir(path)
    download()


# ------ Split the original retweet cascades
train_cascades, test_cascades, ids = split_train_and_test("total.txt")

# ------ Store the cascades
print("Size of train:", len(train_cascades))
print("Size of test:", len(test_cascades))

with open("train_cascades.txt", "w") as f:
    for cascade in train_cascades:
        f.write(cascade + "\n")

with open("test_cascades.txt", "w") as f:
    for cascade in test_cascades:
        f.write(cascade + "\n")

# ------ Store the active ids
f = open("active_users.txt", "w")
for uid in ids:
    f.write(uid + "\n")
f.close()

# ------ Keep the subnetwork of the active users
g = open("weibo_network.txt", "w")

f = open("graph_170w_1month.txt", "r")

found = 0
idx = 0
for line in f:
    edge = line.replace("\n", "").split(" ")

    if edge[0] in ids and edge[1] in ids and edge[2] == '1':
        found += 1
        g.write(line)
    idx += 1
    if (idx % 2000000 == 0):
        print(idx)
        print(found)
        print("---------")

g.close()

f.close()


