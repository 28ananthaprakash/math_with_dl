# -*- coding: utf-8 -*-
'''
Author : Ananthaprakash T
'''
# Commented out IPython magic to ensure Python compatibility.
from __future__ import absolute_import, division, print_function, unicode_literals


#import tensorflow as tf
import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from sklearn.model_selection import train_test_split

import unicodedata
import re
import numpy as np
import os
import io
import time
import pandas as pd

tf.__version__

messages = ['1+1','2+2','3+3','4+4','5+5','6+6','7+7','8+8','9+9','10+10']
responses = ['2','4','6','8','10','12','14','16','18','20']
# Converts the unicode file to ascii
def unicode_to_ascii(s):
  return ''.join(c for c in unicodedata.normalize('NFD', s)
      if unicodedata.category(c) != 'Mn')


def preprocess_sentence(w):
  return w

# Creating the dataset

def create_dataset(messages,responses,num_examples=None):
  new_data=[]
  for message, response in zip(messages,responses):
    message=preprocess_sentence(message)
    response=preprocess_sentence(response)
    new_data.append([message,response])
  new_data=new_data[:num_examples]
  return zip(*new_data)



def tokenize(lang1, lang2):
  lang1len=len(lang1)
  lang1=list(lang1)
  lang2=list(lang2)
  lang1.extend(lang2)
  lang_tokenizer = tf.keras.preprocessing.text.Tokenizer(
      filters='')
  lang1=tuple(lang1)
  lang_tokenizer.fit_on_texts(lang1)

  tensor = lang_tokenizer.texts_to_sequences(lang1)

  tensor = tf.keras.preprocessing.sequence.pad_sequences(tensor,padding='post')#padding in pre or post
  tensor1 = tensor[:lang1len]
  tensor2 = tensor[lang1len:]

  return tensor1,tensor2, lang_tokenizer


questions_1000, answers_1000 = create_dataset(messages,responses,num_examples=None)
qseq , aseq, words = tokenize(questions_1000,answers_1000)


a=0
for i in qseq:
  for j in i:
    if a<j:
      a=j
qvocab=a
b=0
for i in aseq:
  for j in i:
    if b<j:
      b=j
avocab=b
#c=max(a,b)
#c
vocab_size_calc = max(avocab,qvocab)

#words.index_word[26654]
print(vocab_size_calc)


# Helper Function

"""

Helper Fulctions

"""

import numpy as np

def batch1(inputs, max_sequence_length=None):
    """
    Args:
        inputs:
            list of sentences (integer lists)
        max_sequence_length:
            integer specifying how large should `max_time` dimension be.
            If None, maximum sequence length would be used
    
    Outputs:
        inputs_time_major:
            input sentences transformed into time-major matrix 
            (shape [max_time, batch_size]) padded with 0s
        sequence_lengths:
            batch-sized list of integers specifying amount of active 
            time steps in each input sequence
    """
    
    sequence_lengths = [len(seq) for seq in inputs]
    batch_size = len(inputs)
    
    #Taking the largest list
    if max_sequence_length is None:
        max_sequence_length = max(sequence_lengths) 
    #Creating the matrix for [100,5] with zeros
    inputs_batch_major = np.zeros(shape=[batch_size, max_sequence_length], dtype=np.int32) # == PAD
    
    for i, seq in enumerate(inputs):
        for j, element in enumerate(seq):
            inputs_batch_major[i, j] = element

    # [batch_size, max_time] -> [max_time, batch_size]
    inputs_time_major = inputs_batch_major.swapaxes(0, 1)

    return inputs_time_major, sequence_lengths


def random_sequences(length_from, length_to,
                     vocab_lower, vocab_upper,
                     batch_size):
    """ Generates batches of random integer sequences,
        sequence length in [length_from, length_to],
        vocabulary in [vocab_lower, vocab_upper]
    """
    #if length_from > length_to:
            #raise ValueError('length_from > length_to')

    def random_length():
        if length_from == length_to:
            return length_from
        return np.random.randint(length_from, length_to)
    
    while True:
        yield [
            np.random.randint(low=vocab_lower,
                              high=vocab_upper,
                              size=random_length()).tolist()
            for _ in range(batch_size)
        ]

def make_batch(data,batch_size):
  x=[]
  y=[]
  for i,j in enumerate(data):
    i=i+1
    y.append(list(j))
    if i%batch_size == 0:
      x.append(y)
      y=[]
  return iter(x)

def batch2(input_tensor_train):
  seq_len=[]
  for ls in input_tensor_train:
    tmp=0
    for val in ls:
      if val !=0:
        tmp+=1
    seq_len.append(tmp)
  inputs_time_major = np.array(input_tensor_train).swapaxes(0, 1)
  return inputs_time_major , seq_len

'''a1=[[1,2],[3,4],[5,6],[7,8]]
a1=np.array(a1)
z1 = np.zeros(a1.shape)
z1

b1=np.append(a1,z1,axis=1)
b1'''

'''a0 = make_batch(qseq,10)
batch2(next(a0))'''

# SEQ2SEQ model def

tf.__version__
sess = tf.InteractiveSession()

#First critical thing to decide: vocabulary size.
#Dynamic RNN models can be adapted to different batch sizes 
#and sequence lengths without retraining 
#(e.g. by serializing model parameters and Graph definitions via tf.train.Saver), 
#but changing vocabulary size requires retraining the model.



PAD = 0
EOS = 1

vocab_size = vocab_size_calc
input_embedding_size = 28 #max([max([len(k) for k in qseq]),max([len(k) for k in aseq])]) #character length

encoder_hidden_units = 1000 #num neurons
decoder_hidden_units = encoder_hidden_units * 2 #in original paper, they used same number of neurons for both encoder
#and decoder, but we use twice as many so decoded output is different, the target value is the original input 
#in this example

encoder_inputs = tf.placeholder(shape=(None, None), dtype=tf.int32, name='encoder_inputs')
#contains the lengths for each of the sequence in the batch, we will pad so all the same
#if you don't want to pad, check out dynamic memory networks to input variable length sequences
encoder_inputs_length = tf.placeholder(shape=(None,), dtype=tf.int32, name='encoder_inputs_length')
decoder_targets = tf.placeholder(shape=(None, None), dtype=tf.int32, name='decoder_targets')

#randomly initialized embedding matrrix that can fit input sequence
#used to convert sequences to vectors (embeddings) for both encoder and decoder of the right size
#reshaping is a thing, in TF you gotta make sure you tensors are the right shape (num dimensions)
embeddings = tf.Variable(tf.random_uniform([vocab_size, input_embedding_size], -1.0, 1.0), dtype=tf.float32)
#this thing could get huge in a real world application
encoder_inputs_embedded = tf.nn.embedding_lookup(embeddings, encoder_inputs)

from tensorflow.python.ops.rnn_cell import LSTMCell, LSTMStateTuple

encoder_cell = LSTMCell(encoder_hidden_units)

#get outputs and states
#bidirectional RNN function takes a separate cell argument for 
#both the forward and backward RNN, and returns separate 
#outputs and states for both the forward and backward RNN

#When using a standard RNN to make predictions we are only taking the “past” into account. 
#For certain tasks this makes sense (e.g. predicting the next word), but for some tasks 
#it would be useful to take both the past and the future into account. Think of a tagging task, 
#like part-of-speech tagging, where we want to assign a tag to each word in a sentence. 
#Here we already know the full sequence of words, and for each word we want to take not only the 
#words to the left (past) but also the words to the right (future) into account when making a prediction. 
#Bidirectional RNNs do exactly that. A bidirectional RNN is a combination of two RNNs – one runs forward from 
#“left to right” and one runs backward from “right to left”. These are commonly used for tagging tasks, or 
#when we want to embed a sequence into a fixed-length vector (beyond the scope of this post).


((encoder_fw_outputs,
  encoder_bw_outputs),
 (encoder_fw_final_state,
  encoder_bw_final_state)) = (
    tf.nn.bidirectional_dynamic_rnn(cell_fw=encoder_cell,
                                    cell_bw=encoder_cell,
                                    inputs=encoder_inputs_embedded,
                                    sequence_length=encoder_inputs_length,
                                    dtype=tf.float32, time_major=True)
    )

#Concatenates tensors along one dimension.
encoder_outputs = tf.concat((encoder_fw_outputs, encoder_bw_outputs), 2)

#letters h and c are commonly used to denote "output value" and "cell state". 
#http://colah.github.io/posts/2015-08-Understanding-LSTMs/ 
#Those tensors represent combined internal state of the cell, and should be passed together. 

encoder_final_state_c = tf.concat(
    (encoder_fw_final_state.c, encoder_bw_final_state.c), 1)

encoder_final_state_h = tf.concat(
    (encoder_fw_final_state.h, encoder_bw_final_state.h), 1)

#TF Tuple used by LSTM Cells for state_size, zero_state, and output state.
encoder_final_state = LSTMStateTuple(
    c=encoder_final_state_c,
    h=encoder_final_state_h
)

decoder_cell = LSTMCell(decoder_hidden_units)


#we could print this, won't need
encoder_max_time, batch_size = tf.unstack(tf.shape(encoder_inputs))

batch_size

decoder_lengths = encoder_inputs_length + 3
# +2 additional steps, +1 leading <EOS> token for decoder inputs


#manually specifying since we are going to implement attention details for the decoder in a sec
#weights
W = tf.Variable(tf.random_uniform([decoder_hidden_units, vocab_size], -1, 1), dtype=tf.float32)
#bias
b = tf.Variable(tf.zeros([vocab_size]), dtype=tf.float32)

#create padded inputs for the decoder from the word embeddings

#were telling the program to test a condition, and trigger an error if the condition is false.
assert EOS == 1 and PAD == 0

eos_time_slice = tf.ones([batch_size], dtype=tf.int32, name='EOS')
pad_time_slice = tf.zeros([batch_size], dtype=tf.int32, name='PAD')

#retrieves rows of the params tensor. The behavior is similar to using indexing with arrays in numpy
eos_step_embedded = tf.nn.embedding_lookup(embeddings, eos_time_slice)
pad_step_embedded = tf.nn.embedding_lookup(embeddings, pad_time_slice)


#manually specifying loop function through time - to get initial cell state and input to RNN
#normally we'd just use dynamic_rnn, but lets get detailed here with raw_rnn

#we define and return these values, no operations occur here
def loop_fn_initial():
    initial_elements_finished = (0 >= decoder_lengths)  # all False at the initial step
    #end of sentence
    initial_input = eos_step_embedded
    #last time steps cell state
    initial_cell_state = encoder_final_state
    #none
    initial_cell_output = None
    #none
    initial_loop_state = None  # we don't need to pass any additional information
    return (initial_elements_finished,
            initial_input,
            initial_cell_state,
            initial_cell_output,
            initial_loop_state)

#attention mechanism --choose which previously generated token to pass as input in the next timestep
def loop_fn_transition(time, previous_output, previous_state, previous_loop_state):

    
    def get_next_input():
        #dot product between previous ouput and weights, then + biases
        output_logits = tf.add(tf.matmul(previous_output, W), b)
        #Logits simply means that the function operates on the unscaled output of 
        #earlier layers and that the relative scale to understand the units is linear. 
        #It means, in particular, the sum of the inputs may not equal 1, that the values are not probabilities 
        #(you might have an input of 5).
        #prediction value at current time step
        
        #Returns the index with the largest value across axes of a tensor.
        prediction = tf.argmax(output_logits, axis=1)
        #embed prediction for the next input
        next_input = tf.nn.embedding_lookup(embeddings, prediction)
        return next_input
    
    
    elements_finished = (time >= decoder_lengths) # this operation produces boolean tensor of [batch_size]
                                                  # defining if corresponding sequence has ended

    
    
    #Computes the "logical and" of elements across dimensions of a tensor.
    finished = tf.reduce_all(elements_finished) # -> boolean scalar
    #Return either fn1() or fn2() based on the boolean predicate pred.
    input = tf.cond(finished, lambda: pad_step_embedded, get_next_input)
    
    #set previous to current
    state = previous_state
    output = previous_output
    loop_state = None

    return (elements_finished, 
            input,
            state,
            output,
            loop_state)

def loop_fn(time, previous_output, previous_state, previous_loop_state):
    if previous_state is None:    # time == 0
        assert previous_output is None and previous_state is None
        return loop_fn_initial()
    else:
        return loop_fn_transition(time, previous_output, previous_state, previous_loop_state)

#Creates an RNN specified by RNNCell cell and loop function loop_fn.
#This function is a more primitive version of dynamic_rnn that provides more direct access to the 
#inputs each iteration. It also provides more control over when to start and finish reading the sequence, 
#and what to emit for the output.
#ta = tensor array
decoder_outputs_ta, decoder_final_state, _ = tf.nn.raw_rnn(decoder_cell, loop_fn)
decoder_outputs = decoder_outputs_ta.stack()

#to convert output to human readable prediction
#we will reshape output tensor

#Unpacks the given dimension of a rank-R tensor into rank-(R-1) tensors.
#reduces dimensionality
decoder_max_steps, decoder_batch_size, decoder_dim = tf.unstack(tf.shape(decoder_outputs))
#flettened output tensor
decoder_outputs_flat = tf.reshape(decoder_outputs, (-1, decoder_dim))
#pass flattened tensor through decoder
decoder_logits_flat = tf.add(tf.matmul(decoder_outputs_flat, W), b)
#prediction vals
decoder_logits = tf.reshape(decoder_logits_flat, (decoder_max_steps, decoder_batch_size, vocab_size))

#final prediction
decoder_prediction = tf.argmax(decoder_logits, 2)

#cross entropy loss
#one hot encode the target values so we don't rank just differentiate
stepwise_cross_entropy = tf.nn.softmax_cross_entropy_with_logits(
    labels=tf.one_hot(decoder_targets, depth=vocab_size, dtype=tf.float32),
    logits=decoder_logits,
)

#loss function
loss = tf.reduce_mean(stepwise_cross_entropy)
#train it 
train_op = tf.train.AdamOptimizer().minimize(loss)

sess.run(tf.global_variables_initializer())

# Defining Batch



batch_size = 2

'''batches = random_sequences(length_from=3, length_to=8,
                                   vocab_lower=2, vocab_upper=10,
                                   batch_size=batch_size)
'''
batches = make_batch(qseq,batch_size)
print('head of the batch:')
for seq in next(batches)[:10]:
    print(seq)
batches = make_batch(qseq,batch_size)
#batches = make_batch(input_tensor_train,100)


def next_feed():
  #try:
  batch = next(batches)
  #except:
    #pass
  encoder_inputs_, encoder_input_lengths_ = batch1(batch)
  #print(encoder_inputs_, encoder_input_lengths_)
  decoder_targets_, _ = batch1(
        [(sequence) + [EOS] + [PAD] * 2 for sequence in batch]
  )
  #print(decoder_targets)
  return {
        encoder_inputs: encoder_inputs_,
        encoder_inputs_length: encoder_input_lengths_,
        decoder_targets: decoder_targets_,
  }

qbatches = make_batch(qseq,batch_size)
abatches = make_batch(aseq,batch_size)
def next_feed_chat():
  #try:
  qbatch = next(qbatches)
  abatch = next(abatches)
  #except:
    #pass
  encoder_inputs_, encoder_input_lengths_ = batch1(qbatch)
  #print(encoder_inputs_, encoder_input_lengths_)
  decoder_targets_, _ = batch1(
        [(sequence) + [EOS] + [PAD] * 2 for sequence in abatch]
  )
  #print(decoder_targets)
  return {
        encoder_inputs: encoder_inputs_,
        encoder_inputs_length: encoder_input_lengths_,
        decoder_targets: decoder_targets_,
  }

'''b=next_feed_chat()
b[decoder_targets]'''

#len(b[decoder_targets])

'''c=next_feed()
c[decoder_targets]'''

loss_track = []

max_batches = 5 #3001
batches_in_epoch = 2
#epoch__ = 2
for i in range(10):
  qbatches = make_batch(qseq,batch_size)
  abatches = make_batch(aseq,batch_size)
  try:
    for batch in range(max_batches):
        fd = next_feed_chat()
        _, l = sess.run([train_op, loss], fd)
        loss_track.append(l)

        if batch == 0 or batch % batches_in_epoch == 0:
            print('batch {}'.format(batch))
            print('  minibatch loss: {}'.format(sess.run(loss, fd)))
            predict_ = sess.run(decoder_prediction, fd)
            for i, (inp, pred) in enumerate(zip(fd[encoder_inputs].T, predict_.T)):
                print('  sample {}:'.format(i + 1))
                print('    input     > {}'.format(inp))
                print('    predicted > {}'.format(pred))
                zz=[]
                for z in inp:
                  if z != 0:
                    zz.append(words.index_word[z])
                print(zz)
                zz=[]
                for z in pred:
                  if z != 0:
                    zz.append(words.index_word[z])
                print(zz)
                if i >= 2:
                    break
            print()

  except KeyboardInterrupt:
    print('training interrupted')



import matplotlib.pyplot as plt
# %matplotlib inline

plt.plot(loss_track)
