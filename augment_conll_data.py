import collections
import sys
import re
import coref_lib


label_splitter = re.compile("([0-9]+|\(|\))")

def format_label(next_coref_field, curr_entities):

  # Entities whose spans end at this token
  to_end = set()

  # Split out parens and entity numbers
  contents = re.findall(label_splitter, next_coref_field)

  while contents:
    elem = contents.pop(0)

    if elem == "(":
      # Should start a new entity span
      num = contents.pop(0)
      assert num.isdigit()
      curr_entities.add(
          coref_lib.TokenLabel(
            coref_lib.BIOLabels.B, num))

      if contents:
        # Check for single-token mentions
        maybe_close_brace = contents.pop(0)
        if maybe_close_brace == ")":
          to_end.add(num)
        else:
          contents.insert(0, maybe_close_brace)

    elif elem != ")":
      # Check for span ending
      close_brace = contents.pop(0)
      assert close_brace == ")"
      to_end.add(elem)

  final_labels = "|".join(sorted(x.bio + '-' + x.entity
      for x in curr_entities))
  if not final_labels:
    final_labels = "_"

  curr_entities = set([coref_lib.change_label(
    coref_lib.BIOLabels.I, label)
      for label in curr_entities
      if label.entity not in to_end])

  return curr_entities, final_labels


def main():

  conll_file, dep_file = sys.argv[1:]
  out_file = conll_file.replace(".txt", "_aug.txt")
  sentences = []
  curr_entities = set()

  dep_file_lines = []
  with open(dep_file, 'r') as f:
    for line in f:
      dep_file_lines.append(line)

  conll_file_lines = []
  with open(conll_file, 'r') as f:
    for line in f:
      if not line.startswith("#"):
        conll_file_lines.append(line)

  with open(out_file, 'w') as f_out:
    for dep_line, conll_line in zip(dep_file_lines, conll_file_lines):
      fields = conll_line.split()
      if not len(fields):
        assert not dep_line.strip()
        f_out.write(line)
        # Start a new sentence
        curr_entities = set()
      else:
        curr_entities, new_label = format_label(fields[-1], curr_entities)

        dep_fields = dep_line.split()

        (doc_id, doc_part, token_idx, token, pos, cparse,
            _, _, _, speaker) = fields[:10]
        coref_label = fields[-1]
        (dep_idx, dep_token, _, pos_1, pos_2, _, dep_parent,
            dep_arc, _, _) = dep_fields
        assert (token == dep_token) or (token.replace("/", "").replace("\\", "") == dep_token)
        assert pos == pos_2
        assert int(dep_idx) == int(token_idx) + 1

        new_fields = [doc_id, doc_part, token_idx, token, pos, cparse, dep_idx,
            dep_token, pos_1, dep_parent, dep_arc] + fields[6:] + [coref_label, new_label]

        output = "\t".join(new_fields)
        f_out.write(output + "\n")


if __name__ == "__main__":
  main()

