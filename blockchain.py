# Importing the libraries
import datetime
import hashlib
import json
from flask import Flask, jsonify, request
import requests
from uuid import uuid4
from urllib.parse import urlparse
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import load_pem_public_key

# Blockchain Class
class Blockchain:
    # The constructor
    def __init__(self, esc_code, dsc_code):
        """
        Initializes the blockchain.
        """
        self.chain = []                                             # List of block objects (belonging to the blockchain)
        self.transaction_pool = [{'esc': esc_code},                 # Store the ESC bytecode
                                {'dsc': dsc_code}]                  # Store the DSC bytecode

        self.create_block(previous_hash='0')                        # Creating the Genesis block
        self.nodes = {'146.122.195.103:901'}                        # Set of neighbouring district nodes

    def create_block(self, previous_hash):
        """
        Returns the new blockchain that contains the latest transactions from the
        transaction_pool in a newly validated block.
        """
        if len(self.transaction_pool) < 1:
            return None, None

        # Create A Temporary Block
        block = {'index': None,                                 # before mining set index to None
                 'timestamp': None,                             # before mining set timestamp to None
                 'nonce': 0,                                    # before mining set nonce to 0
                 'transactions': self.transaction_pool,         # Fill in all the transactions
                 'previous_hash': previous_hash,                # Set the previous hash
                 'current_hash': ''}                            # Current hash is yet to be calculated

        # Empty Transaction Pool
        self.transaction_pool = []                  # Once transactions have been placed in a block
                                                    # they can be removed from the pool

        # Calculate Proof Of Work (Nonce)
        block['nonce'], block['current_hash'] = self.proof_of_work(block, previous_hash)        # Validate the block by calculating the nonce
        block['index'] =  len(self.chain) + 1                                                   # Set the block index
        block['timestamp'] = str(datetime.datetime.now())                                       # Set the timestamp to the time when the block was validated

        # Add Block To DistrictNode's Own Chain
        self.chain.append(block)                    # Append the block to the list of blocks in the blockchain
        print("BLOCK ADDED TO 90")
        for block in self.chain:
            for key, value in block.items():
                print(key, value)
            print('\n')

        return self.chain, self.transaction_pool    # Return the new chain and the new transaction_pool

    def get_max_transaction_pool_length(self):
        return 2

    def get_previous_block(self):
        """
        Returns the last block in the blockchain.
        """
        return self.chain[-1]                       # Return the previous block

    def proof_of_work(self, block, previous_hash):
        """
        Validates a new block by calculating a nonce that helps
        meeting the condition on the current_hash.
        """
        # Start WIth Nonce = 1
        nonce = 1

        # Loop Till You Find A Valid Nonce
        check_proof = False
        while check_proof is False:
            block['nonce'] = nonce
            hash_operation = self.hash(block)
            if hash_operation[:4] == '0000':            # Check if the current_hash fulfills the required condition
                check_proof = True                      # If it does then exit the loop
            else:
                nonce += 1                              # Else try with the next nonce

        return nonce, hash_operation                    # Return the nonce and the hash that meet the required condition

    def hash(self, block):
        """
        Calculates the hash using SHA-256.
        The hash comprises of the nonce, transactions and the previous_hash.
        """
        # Convert Dictionary To String

        encoded_block = json.dumps({'nonce': block['nonce'],                                            # Create a string from the required fields
                                    'transaction': block['transactions'],
                                    'previous_hash': block['previous_hash']}, sort_keys=True).encode()

        # Hash The String And Return It
        return hashlib.sha256(encoded_block).hexdigest()    # Return the hash

    def is_chain_valid(self, chain):
        """
        Calculates if the chain is consistent.
        - checks if previous_hash of current block is equal to current_hash of previous_block
        - checks if current_hash of each block matches the required condition on hashes
        """
        previous_block = chain[0]
        block_index = 1
        while block_index < len(chain):
            block = chain[block_index]
            if block['previous_hash'] != self.hash(previous_block):
                return False
            previous_proof = previous_block['proof']
            proof = block['proof']
            hash_operation = self.hash(block)
            if hash_operation[:4] != '0000':
                return False
            previous_block = block
            block_index += 1
        return True

    def add_transaction(self, transaction, signature, client_public_key):
        """
        Add a transaction to the local transaction_pool after verifying its signature.
        """
        # Check If transaction is already in the transaciton_pool
        if transaction not in self.transaction_pool:
            # Verify With All Other Nodes
            if self.verify_transaction(transaction, signature, client_public_key):
                # Encrypt the transaction
                client_public_key = load_pem_public_key(client_public_key, default_backend())
                encrypted_transaction = client_public_key.encrypt(
                    json.dumps(transaction).encode(),
                    padding.OAEP(
                        mgf = padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm = hashes.SHA256(),
                        label = None
                    )
                )

                self.transaction_pool.append(str(encrypted_transaction))

            else: return False, self.transaction_pool  # Return False if Verification fails

        # Return True if transaction was already in transaction_pool or if verification was successful and new transaction was added
        return True, self.transaction_pool

    def verify_transaction(self, transaction, signature, client_public_key):
        # Generate Public Key From Public Key String
        client_public_key = load_pem_public_key(client_public_key, default_backend())

        # Verify the signature
        try:
            client_public_key.verify(
                signature,
                json.dumps(transaction).encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            print('Valid Signature!!')
        except InvalidSignature:
            print('Invalid Signature!!')
            return False                    # Return False if the verification failed

        return True                         # Return True if the verification was successful


    def add_node(self, address):
        """
        Add a neighbouring node to the current_node
        """
        parsed_url = urlparse(address)

        # Add Neighbour Node's IP address to nodes list
        self.nodes.add(parsed_url.netloc)

    def replace_chain(self):
        network = self.nodes
        longest_chain = None
        max_length = len(self.chain)
        for node in network:
            response = requests.get(f'http://{node}/get_chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                if length > max_length and self.is_chain_valid(chain):
                    max_length = length
                    longest_chain = chain
        if longest_chain:
            self.chain = longest_chain
            return True
        return False