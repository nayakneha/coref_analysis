import collections
import nltk
import re

class BIOLabels(object):
  B = "B"
  I = "I"
  O = "O"


class TokenLabel(object):
  def __init__(self, bio, entity):
    self.bio = bio
    self.entity = entity

# ====================== Parse processing ===================================


def get_parse(parser, sentence):
  result = parser.raw_parse(sentence)
  parse = next(result)
  return parse

def indexify(index, word):
  return str(index) + "_" + word

def unindexify(indexed_word):
  str_index, word = indexed_word.split("_")
  return int(str_index), word

def enumerate_parse(node, token_list, index=0):
  if len(node) == 1 and type(node[0]) == str:
    (maybe_word, ) = node
    i_word = indexify(index, maybe_word)
    _ = node.pop(0)
    node.insert(0, i_word)
    token_list.append(i_word)
    return index + 1
  else:
    for child in node:
      index = enumerate_parse(child, token_list, index)
    return index


def get_span(node):
  label = node.label()
  nodes = [node]
  tokens = []
  while nodes:
    curr_node = list(nodes.pop(0))
    if len(curr_node) == 1 and type(curr_node[0]) == str:
      (maybe_word, ) = curr_node
      tokens.append(maybe_word)
    else:
      child_list = [i for i in curr_node]
      nodes = child_list + nodes

  just_tokens = [x.split("_")[1] for x in tokens]
  start_token = int(tokens[0].split("_")[0])
  end_token = int(tokens[-1].split("_")[0])
  return  (start_token, end_token), label, just_tokens

def get_all_spans(parse, span_list):
  idxs, label, tokens = get_span(parse)
  span_list[idxs] = (label, tokens)
  for child in parse:
    if type(child)  != str:
      get_all_spans(child, span_list)


# ====================== Coref processing ===================================

label_splitter = re.compile("([0-9]+|\(|\))")

def get_entities_from_label(label):
  curr_entities = []
  to_end = []
  contents = re.findall(label_splitter, label)
  while contents:
    elem = contents.pop(0)
    if elem == "(":
      # Should start a new entity span
      num = contents.pop(0)
      assert num.isdigit()
      curr_entities.append(num)

      if contents:
        # Check for single-token mentions
        maybe_close_brace = contents.pop(0)
        if maybe_close_brace == ")":
          to_end.append(num)
        else:
          contents.insert(0, maybe_close_brace)

    elif elem != ")":
      # Check for span ending
      close_brace = contents.pop(0)
      assert close_brace == ")"
      to_end.append(elem)
  return curr_entities, to_end

def change_label(bio_label, token_label):
  token_label.bio = bio_label
  return token_label

class Sentence(object):
  def __init__(self, lines, idx):
    sequences = list(zip(*[line.strip().split() for line in lines]))
    coref_tags = [line.strip().split("\t")[:1] for line in lines]

    (document_ids, _, _, tokens, pos, cparse) = sequences[0:6]
    coref_tags = sequences[-1]
    self.tokens = tokens

    assert len(set(document_ids)) == 1
    self.document_id = document_ids[0]
    self.idx = idx
    self.sentence_id = self.document_id + "_" + str(self.idx).zfill(4)

    #self.dep_tree = self.make_dep_tree()
    self.con_tree = self.make_con_tree(cparse, pos, tokens)
    #self.con_spans = self.get_con_spans()
    self.coref_spans = self.get_coref_spans(tokens, coref_tags)

    token_list = []
    enumerate_parse(self.con_tree, token_list)
    self.parse_spans = {}
    get_all_spans(self.con_tree, self.parse_spans)
    self.match_spans()

  def match_spans(self):
    for span, entities in self.coref_spans.items():
      (first, last) = span
      if span in self.parse_spans:
        tree_label, tokens = self.parse_spans[span]
        print("\t".join(["Y", str(first), str(last), "|".join(entities), tree_label, " ".join(tokens)]))
      else:
        print("\t".join(["N", str(first), str(last), "|".join(entities), "-", " ".join(self.tokens[first:last + 1])]))

  def make_con_tree(self, cparse, pos, tokens):
    new_cparse = ""
    for i, fragment in enumerate(" ".join(cparse).split("*")):
      new_cparse += fragment
      if i == len(tokens):
        break
      new_cparse += "".join(["(", pos[i], " ", tokens[i], ")"])

    return nltk.tree.ParentedTree.fromstring(new_cparse)

  def get_coref_spans(self, tokens, labels):
    span_map = collections.defaultdict(list)
    open_spans = collections.defaultdict(list)
    for i, (token, label) in enumerate(zip(tokens, labels)):
      span_starts, span_ends = get_entities_from_label(label)
      for label in span_starts:
        open_spans[label].append(i)
      for label in span_ends:
        open_idx = open_spans[label].pop(-1)
        label_span = (open_idx, i)
        span_map[label_span].append(label)
    return span_map





class Document(object):
  def __init__(self, input_sentence_lines):
    self.sentences = []
    for i, sentence_lines in enumerate(input_sentence_lines):
      self.sentences.append(Sentence(sentence_lines, i))


  def create_e2e_input(self):
    pass


class Dataset(object):
  """ Get documents from preprocessed (BIO + deps) file."""
  def __init__(self, filename):
    self.documents = self.get_documents_from_file(filename)

  def get_documents_from_file(self, filename):

    curr_sentence = []
    curr_doc = []
    curr_doc_id = None
    doc_lines = []

    with open(filename, 'r') as f:
      for line in f:
        if line.startswith("#"):
          continue
        if not line.strip():
          curr_doc.append(curr_sentence)
          curr_sentence = []
        else:
          curr_sentence.append(line)
          fields = line.strip().split()
          doc_id = fields[0]
          if curr_doc_id is not None:
            if doc_id != curr_doc_id:
              doc_lines.append(curr_doc)
              curr_doc = []
          curr_doc_id = doc_id

    documents = []
    for single_doc_lines in doc_lines:
      documents.append(Document(single_doc_lines))
