from blockchain import Blockchain
from flask import Flask, render_template, request
import requests
import hashlib
import json
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import load_pem_public_key

# Create a Flask App to handle HTTP Requests
app = Flask(__name__)

# Fetch the ESC and DSC bytecode
SC_CODE_DIR = '.'
ESC_CODE_FILE = 'ESC.py'
DSC_CODE_FILE = 'DSC.py'

esc_bytecode = open(os.path.join(SC_CODE_DIR, ESC_CODE_FILE), 'r').read()
dsc_bytecode = open(os.path.join(SC_CODE_DIR, DSC_CODE_FILE), 'r').read()

# Instantiate the blockchain
block_chain = Blockchain(esc_bytecode, dsc_bytecode)

# Handle a POST request on /add_transaction
@app.route('/add_transaction', methods = ['POST'])
def add_transaction():
    """
    Voter To DN

    Recieves a transaction (Vote) from the voter / client.
    Verifies the signature.
    Adds the transaction to the local transaction_pool.
    Boradcasts the transaction to neighbour nodes.
    Validates and creates a new block.
    Broadcast the chain.
    """

    # Store the data received from the POST request in temporary files
    with open('90/temporary_transactions.json', 'wb') as f:
        f.write(request.files['transactions'].read())

    with open('90/temporary_signature', 'wb') as f:
        f.write(request.files['signature'].read())

    with open('90/temporary_public_key', 'wb') as f:
        f.write(request.files['public_key'].read())

    # Open the files
    transaction_file = open('90/temporary_transactions.json', 'rb')
    signature_file = open('90/temporary_signature', 'rb')
    public_key_file = open('90/temporary_public_key', 'rb')

    # convert the file contents into the expected formats
    transaction = json.load(transaction_file)               # Convert to json
    signature = signature_file.read()                       # Fetch the signature as 'bytes'
    client_public_key = public_key_file.read()              # Fetch the public key as 'bytes'

    # Open new file instances
    transaction_file = open('90/temporary_transactions.json', 'rb')
    signature_file = open('90/temporary_signature', 'rb')
    public_key_file = open('90/temporary_public_key', 'rb')

    # Add the transaction to the local transaction_pool
    success, transaction_pool = block_chain.add_transaction(transaction, signature, client_public_key)

    if success:  # 1 transaction per block for now so start mining immediately
        broadcast_transaction(transaction_file, public_key_file, signature_file)
        # PoW (Create a block)

        previous_block = block_chain.get_previous_block()
        chain, transaction_pool = block_chain.create_block(previous_block['current_hash'])

        if chain:
            broadcast_chain(chain, transaction_pool)      # Broadcast the updated chain to neighbour nodes
    else:
        print('Failiure in transaction add!')
        browser_response = 'FAILURE'
        return browser_response, 400

    browser_response = 'SUCCESS'
    return browser_response, 200    # Return a successful response

def broadcast_transaction(transaction_file, public_key_file, signature_file):
    """
    Helper function to broadcast the transaction to neighbouring nodes.
    """
    for node in block_chain.nodes:
        broadcast_response = requests.post('http://' + node + '/receive_transaction',
                                           files={"public_key": public_key_file,
                                                  "signature": signature_file, "transactions": transaction_file})


def broadcast_chain(chain, transaction_pool):
    """
    Helper function to broadcast the blockchain to neighbouring nodes.
    """
    for node in block_chain.nodes:
        broadcast_response = requests.post('http://' + node + '/receive_blockchain', json = {'chain': chain,
                                                                                             'transaction_pool': transaction_pool})


# Handle a POST request on /receive_transaction
@app.route('/receive_transaction', methods = ['POST'])
def receive_transaction():
    """
    DN To DN

    Receive the broadcasted transaction from neighbour nodes.
    Verifies the signature.
    Adds the transaction to the local transaction_pool.
    Validates and creates a new block.
    Broadcast the new chain.
    """

    # Fetch data from POST Request
    transaction = json.load(request.files['transactions'])
    signature = request.files['signature'].read()
    client_public_key = request.files['public_key'].read()

    # Add transaction to local transaction_pool
    success, transaction_pool = block_chain.add_transaction(transaction, signature, client_public_key)

    if success: # 1 transaction per block for now so start validating immediately
        # PoW (Create a block)
        previous_block = block_chain.get_previous_block()
        chain, transaction_pool = block_chain.create_block(previous_block['current_hash'])

    if chain:
        broadcast_chain(chain, transaction_pool)          # Broadcast the chain to neighbouring nodes

    browser_response = 'SUCCESS'
    return browser_response, 200    # Return a successful response


# Handle a POST request on /receive_blockchain
@app.route('/receive_blockchain', methods = ['POST'])
def receive_blockchain():
    """
    Receive the blockchain that was broadcasted by other nodes
    and update the local blockchain if required
    """


    request.get_json()              # Load the json object from the POST request
    json = request.json             # name the loaded object json

    chain = json['chain']           # load the neighbour's blockchain from the json object
    transaction_pool = json['transaction_pool']             # load the neighbour's transaction_pool from the json object

    if len(block_chain.chain) < len(chain):     # Check if the local blockchain is shorter than neighbour's blockchain
        block_chain.chain = chain               # if so, update the local blockchain
        block_chain.transaction_pool = transaction_pool
    elif len(block_chain.chain) == len(chain):                                      # If the 2 blockchains are of equal length
        if block_chain.get_previous_block()['timestamp'] > chain[-1]['timestamp']:  # and the latest block of the local blockchain is newer
                                                                                    # compared to the latest block of the neighbour's blockchain
            block_chain.chain = chain                                               # replace the latest block of the local blockchain with that of the neighbour's blockchain
            block_chain.transaction_pool = transaction_pool

    browser_response = 'SUCCESS'
    return browser_response, 200        # Return a successful response


@app.route('/get_chain')
def get_chain():
    response = {
        'chain': block_chain.chain,
        'transaction_pool': block_chain.transaction_pool
    }
    return response, 200

# Run the app on 127.0.0.1:90
app.run('146.122.195.103', 900)


