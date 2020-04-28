from flask_socketio import SocketIO, send
from flask import Flask, Response
import requests
import json


app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecret'

socketIo = SocketIO(app, cors_allowed_origins="*")

app.debug = True
app.host = '0.0.0.0'
app.port = '5000'



def get_stances_ucnlp(claim, evidences):
    return requests.post('http://127.0.0.1:6000', json={'claim': claim, 'evidences': evidences})


def get_evidences(claim):
    r = requests.post('http://127.0.0.1:11000', json={'claim': claim})
    similar_lines = r.json()['similar_lines']
    similar_paras = r.json()['similar_paras']
    wiki_results_filtered = r.json()['wiki_results_filtered']
    img_urls = r.json()['img_urls']
    print('get evidences:', 'done')
    return similar_lines, similar_paras, wiki_results_filtered, img_urls



def coreference_resolution(claim):
    r = requests.post('http://127.0.0.1:8000', json={'claim': claim})
    resolved_coref = r.json()['resolved_coref']
    print('resolved coreference:', resolved_coref)
    return resolved_coref

def simplify_sentence(claim):
    r = requests.post('http://127.0.0.1:7000/simplify_sentence', json={'claim': claim})
    claims = r.json()['claims']
    print('simplify sentence:', claims)
    return claims

def generate_questions(claim):
    r = requests.post('http://127.0.0.1:7000/generate_question', json={'claim': claim})
    questions = r.json()['questions']
    gold_answers = r.json()['answers']
    print('generated questions:', questions)
    return questions, gold_answers

def retrieve_answer(question, evidences):
    r = requests.post('http://127.0.0.1:10000/', json={'question': question, 'evidences': evidences})
    answer = r.json()['answer']
    print('retrieve answers:', answer)
    return answer


def get_sentiment_analysis(claim):
    r = requests.post('http://127.0.0.1:9000/sentiment_analysis', json={'text': claim})
    return r.json()

def get_results_gear_api(claim, evidences):
    r = requests.post('http://127.0.0.1:12000/', json={'claim': claim, 'evidences': evidences})
    argmax = r.json()['argmax']
    evidences =r.json()['evidences']
    vals = r.json()['vals']
    print('gear results:', r.json())
    return argmax, evidences, vals


def get_toxicity_scores(claim):
    api_key = 'AIzaSyBTrtgnaWeBx7Z-BMzVS3rL6REJFaaKxaM'
    url = ('https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze' +
           '?key=' + api_key)
    data_dict = {
        'comment': {'text': claim},
        'languages': ['en'],
        'requestedAttributes': {'TOXICITY': {},
                                'SEVERE_TOXICITY': {},
                                'IDENTITY_ATTACK': {},
                                'INSULT': {},
                                'PROFANITY': {},
                                'THREAT': {},
                                'SEXUALLY_EXPLICIT': {},
                                'FLIRTATION': {}}
    }
    response = requests.post(url=url, data=json.dumps(data_dict))
    response_dict = json.loads(response.content)
    attributes = list(response_dict['attributeScores'])
    scores = [item['summaryScore']['value'] for item in list(response_dict['attributeScores'].values())]

    toxicity_scores = {}
    for i in range(len(attributes)):
        toxicity_scores[attributes[i]] = round(scores[i], 2)
        print(f"{attributes[i]}: {round(scores[i], 2)}")

    return toxicity_scores





@socketIo.on("message")
def handleMessage(msg):
    print('something')
    print(msg)

    gear_result_names = ['True', 'Refutes', 'Not enough info']
    claim = msg
    print(claim)

    claim = coreference_resolution(claim)
    claims = simplify_sentence(claim)

    gear_results = []
    generated_questions = []
    predicted_answers = []
    filtered_questions = []

    for claim in claims:
        evidences, paras, wiki_results, img_urls = get_evidences(claim)
        argmax, evidences, vals = get_results_gear_api(claim, evidences)
        print('gear results:', argmax, vals)
        prediction_result = gear_result_names[argmax]

        paras_joined = [' '.join(para) for para in paras]

        if len(evidences) > 0:
            d = {
                'prediction_result': prediction_result,
                'pred_vals': vals,
                'evidences': evidences,
                'paras': paras,
                'wiki_results': wiki_results,
                'paras_joined': paras_joined,
                'img_urls': img_urls
            }
            gear_results.append(d)

        questions, gold_answers = generate_questions(claim)
        generated_questions = generated_questions + questions


        for question in questions:
            if len(paras_joined) > 0:
                answer = retrieve_answer(question, paras_joined)
                filtered_questions.append(question)
                predicted_answers.append(answer)


    qa_pairs = []
    for idx, question in enumerate(filtered_questions):
        qa_pairs.append({'question': question, 'answer': predicted_answers[idx]})

    toxicity_scores = get_toxicity_scores(claim)

    print('sending data..')
    print('questions, answers', qa_pairs)
    print('gear_results:', gear_results)
    print('toxicity scores:', toxicity_scores)

    payload = {
        'qa_pairs': qa_pairs,
        'gear_results': gear_results,
        'toxicity_scores': toxicity_scores
    }
    send(payload, broadcast=True)
    print('done.')
    return None


@app.route('/', methods=['GET', 'POST'])
def answer():
    print('$$$$$$$$$$$$$$$ INSIDE ROUTE $$$$$$$$$$$$$$')
    return Response(
                json.dumps({'key': 'value'}),
                mimetype='application/json',
                headers={
                    'Cache-Control': 'no-cache',
                    'Access-Control-Allow-Origin': '*'
                }
            )


socketIo.run(app)

