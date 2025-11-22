#!/usr/bin/env python

#
# convert 小説家になろう html format into plain text file
#
# this script is forked from the extractor code for ハーメルン
#

import os
import os.path
import sys
import typing
import dataclasses

START_SIG='<div class="js-novel-text p-novel__text">'
EP_TITLE_SIG_TEMPLATE='<a href="/%s/%d/"'

START_EP=1
END_EP=25
NOVEL_ID='n2165ie'

DEBUG=False

@dataclasses.dataclass(frozen=True)
class Tag:
  kind: str
  childs: tuple[typing.Union[typing.Self, str], ...]

def debug(s:str):
  if DEBUG:
    print(f'(DDD): [dropout]: debug: {s}')

def chk_commit_text_child(childs:list[typing.Union[Tag, str]], text_child_buff:list[str]):
  if len(text_child_buff) >0:
    childs.append(''.join(text_child_buff))
    text_child_buff.clear()

def is_kanji_range(c: str)->bool:
  cp=ord(c)

  # https://ja.wikipedia.org/wiki/CJK%E7%B5%B1%E5%90%88%E6%BC%A2%E5%AD%97_(Unicode%E3%81%AE%E3%83%96%E3%83%AD%E3%83%83%E3%82%AF)
  #  CJK統合漢字 (4E00-62FF)
  #  CJK統合漢字 (6300-77FF)
  #  CJK統合漢字 (7800-8CFF)
  #  CJK統合漢字 (8D00-9FFF)
  if cp in range(0x4E00,0x62FF + 1): return True
  if cp in range(0x6300,0x77FF + 1): return True
  if cp in range(0x7800,0x8CFF + 1): return True
  if cp in range(0x8D00,0x9FFF + 1): return True

  return False

def construct_tag(s:str) -> tuple[Tag, int]:
  """return the tag and num of raw char in the xml document that were belong to the parsed tag, continous and counted from the first char in the payload"""
  cursor=0
  need_tag_start=True
  need_tag_kind=False
  tag_kind_buff:list[str]=[]
  tag_kind=None
  tag_kind_now_garbage=False
  need_tag_close=False
  childs:list[typing.Union[Tag, str]]=[]
  text_child_buff:list[str]=[]
  while True:
    a=1 if need_tag_start else 0
    b=1 if need_tag_kind else 0
    c=1 if need_tag_close else 0
    if (a+b+c) != 1:
      print('<EEE>: [dropout]: (internal BUG): deadlock or illegal internal state')
      sys.exit(1)

    if need_tag_start:
      c=s[cursor]
      cursor+=1
      if c!='<':
        print(f'<EEE>: [dropout]: want opening bracket but see {c!r}')
        sys.exit(1)
      need_tag_start=False
      need_tag_kind=True
    else:
      if need_tag_kind:
        try:
          c=s[cursor]  # peek
        except IndexError:
          print('<EEE>: [dropout]: want closing bracket or terminal tag end but early EOF')
          sys.exit(1)
        is_tag_kind_done=is_terminal_tag=False
        if c== '>':
          cursor+=1
          is_tag_kind_done=True
        else:
          subs=s[cursor:]  # peek
          if subs.startswith('/>'):
            # a terminal tag closes right after its tag kind
            is_tag_kind_done=is_terminal_tag=True
            cursor+=2
        if is_tag_kind_done:
          if len(tag_kind_buff) == 0:
            print('<EEE>: [dropout]: empty tag kind')
            sys.exit(1)
          tag_kind=''.join(tag_kind_buff)
          need_tag_kind=False
          if is_terminal_tag:
            for x in (
              'br',
            ):
              if tag_kind == x:
                break
            else:
              print(f'<EEE>: [dropout]: terminal tag syntax but tag kind {tag_kind!r} is not allowed')
              sys.exit(1)
            # terminal tag dont have any child or content, so its now done and we can just return
            return Tag(tag_kind, ()), cursor
          else:
            need_tag_close=True
        elif tag_kind_now_garbage:
          cursor+=1
          # and do nothing, ignore these chars
        else:
          if c == ' ':
            # ignore the properties, for example <div someproperty="value">
            tag_kind_now_garbage=True
            cursor+=1
          elif c in 'abdiprtuvy':  # allowed chars
            tag_kind_buff.append(c)
            cursor+=1
          else:
            print(f'<EEE>: [dropout]: (internal bug): dont know how to deal with char {c!r} living inside tag kind')
            sys.exit(1)
      else:
        if need_tag_close:
          subs=s[cursor:]  # peek
          if subs.startswith('</'):
            cursor+=2
            if tag_kind is None:
              print('<EEE>: [dropout]: (internal bug): going to close the tag, but recorded tag kind was Null')
              sys.exit(1)
            subs=s[cursor:]  # peek
            if not subs.startswith(f'{tag_kind}>'):
              print(f'<EEE>: [dropout]: wanting to close tag of kind {tag_kind!r}, but cant find a valid matching tag end')
              sys.exit(1)
            cursor+=len(tag_kind)+1

            chk_commit_text_child(childs,text_child_buff)  # chk for any dirty buffer

            return Tag(tag_kind, tuple(childs)), cursor
          c=s[cursor]  # peek
          if c == '<':
            # this means an embedded tag inside the current text
            chk_commit_text_child(childs,text_child_buff)  # be sure to do before making new child
            res_tag, how_long = construct_tag(s[cursor:])
            cursor+=how_long
            childs.append(res_tag)
          elif c == '&':
            # special html escaping
            subs=s[cursor:]  # peek
            for x, y in (
              ('&quot;', '"'),
            ):
              if subs.startswith(x):
                cursor+=len(x)
                text_child_buff.append(y)
                break
            else:
              print('<EEE>: [dropout]: missing impl for HTML escaping')
              sys.exit(1)
          elif c in '\n':
            # ignored chars
            cursor += 1
          else:
            # otherwise its considered inner text inside this tag

            cursor+=1

            # 空白 (スペース・全角スペース)
            if c in ' \u3000': text_child_buff.append(c)

            # 句読点・括弧など
            elif c in '、。…‥！!？「」『』()（）《》［］': text_child_buff.append(c)

            # 引用符
            elif c in '“”〝〟＂': text_child_buff.append(c)

            # misc
            elif c in '％～〜＊': text_child_buff.append(c)

            # 長音符
            elif c == 'ー': text_child_buff.append(c)

            # “同じ”
            elif c == '々': text_child_buff.append(c)

            # ダッシュ(?)
            elif c in '─—―': text_child_buff.append(c)

            # 縦棒
            elif c in '｜': text_child_buff.append(c)

            # ハイフン
            elif c in '-': text_child_buff.append(c)

            # コロン
            elif c in '：': text_child_buff.append(c)

            # 数字
            elif c in '1234567890': text_child_buff.append(c)
            # 全角数字
            elif c in '１２３４５６７８９０': text_child_buff.append(c)
            # 丸数字
            elif c in '①②③④⑤⑥⑦⑧⑨⑩': text_child_buff.append(c)

            # ひらがな
            elif c in 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ': text_child_buff.append(c)
            # ひらがな小文字
            elif c in 'ぁぃぅぇぉっゃゅょゎ': text_child_buff.append(c)

            # カタカナ
            elif c in 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ': text_child_buff.append(c)
            # カタカナ小文字
            elif c in 'ァィゥェォッャュョヮ': text_child_buff.append(c)

            # 外来語用
            elif c in 'ゔヴ': text_child_buff.append(c)

            # 漢字
            elif is_kanji_range(c): text_child_buff.append(c)

            # 新字体いろいろ
            elif c in 'ヵヶ': text_child_buff.append(c)

            # アルファベット
            elif c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ': text_child_buff.append(c)
            # 全角アルファベット
            elif c in 'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ': text_child_buff.append(c)

            # ハートマーク
            elif c in '♥♡': text_child_buff.append(c)

            # 音符
            elif c in '♪': text_child_buff.append(c)

            # 中点
            elif c in '・': text_child_buff.append(c)

            # 点・点(全角)
            elif c in '.．': text_child_buff.append(c)

            # まる。
            # (伏せ字用)
            elif c in '○': text_child_buff.append(c)

            # 矢印
            elif c in '＞': text_child_buff.append(c)

            else:
              print(f'<EEE>: [dropout]: (internal bug): dont know how to deal with char {c!r} living inside a tag')
              sys.exit(1)
        else:
          print('unreachable')
          sys.exit(1)

g_known_ruby_tags=set()

def render_ruby(ruby_tag:Tag,buff):
  if ruby_tag not in g_known_ruby_tags:
    g_known_ruby_tags.add(ruby_tag)
    print('<iii>: [dropout]: handling ruby tag:', ruby_tag)
  for child in ruby_tag.childs:
    # there exist two kind of ruby, one of them uses <rb> which is deprecated
    # the code that handles <rb> below is for completeness here only, note that 小説家になろう dont use <rb>
    if isinstance(child, str):
      buff.append(child)
    else:
      # just turn these tag into plain text by removing XML bits, exactly like how it'd work on a browser that dont support ルビ文字
      if child.kind in ('rb', 'rt', 'rp'):
        for inner_child in child.childs:
          if isinstance(inner_child, str):
            buff.append(inner_child)
          else:
            print(f'<EEE>: [dropout]: want text node inside rb/rt tag, got {type(inner_child)!r}')
            sys.exit(1)
      else:
        print(f'<EEE>: [dropout]: cannot render ruby tag: unsupported inner tag {child.kind!r}')
        sys.exit(1)

def parse(s:str) -> str:
  """stateful html parser, return transformed plain text format"""
  buff=[]


  tag, _=construct_tag(s)

  if tag.kind != 'div':
    print(f'<EEE>: [dropout]: expecting the top level tag to be a DIV, got {tag.kind!r}')
    sys.exit(1)

  for child in tag.childs:
    if child.kind != 'p':
      print(f'<EEE>: [dropout]: dont know how to deal with this tag kind inside top level div: {tag.kind!r}')
      sys.exit(1)
    for p_child in child.childs:
      if isinstance(p_child, str):
        buff.append(p_child)
      else:
        assert isinstance(p_child, Tag)
        if p_child.kind=='ruby':
          render_ruby(p_child,buff)
        elif p_child.kind=='br':
          if len(p_child.childs) != 0:
            print('<EEE>: [dropout]: "br" tag is terminal and shouldnt have children')
            sys.exit(1)
          if len(child.childs) == 1:
            pass
            # dont insert a new line here,
            # <br> has no effect if its the only elem inside p
          else:
            buff.append('\n')
        else:
          print(f'<EEE>: [dropout]: only support text node, "br" and ruby tags inside <p>, missing impl for {p_child.kind!r}')
          sys.exit(1)
    # add a new line for every "p" (paragraph) tag
    buff.append('\n')

  return ''.join(buff)

def handle(raw:str, i:int,out_name:str):
  where_start=raw.find(START_SIG)
  if where_start == -1:
    print('<EEE>: [dropout]: cant see start signature, abort.')
    sys.exit(1)
  tr=parse(raw[where_start:])
  print(f'[dropout]: writing result to file {out_name!r}')
  with open(out_name, 'w', encoding='utf-8') as f:
    f.write(tr)

def rename_main(index_html:str):
  titles=[]
  for i in range(START_EP, END_EP + 1):
    sig = EP_TITLE_SIG_TEMPLATE % (NOVEL_ID, i)
    where_a_tag=index_html.find(sig)
    if where_a_tag==-1:
      print(f'<EEE>: [dropout]: cant find episode title signature for Ep. {i}')
      sys.exit(1)
    tag, _ =construct_tag(index_html[where_a_tag:])
    assert tag.kind=='a'
    if len(tag.childs) != 1:
      print(f'<EEE>: [dropout]: cant parse <a> tag for Ep. {i}, expect one text node child, got {len(tag.childs)} childs')
      sys.exit(1)
    if not isinstance(tag.childs[0], str):
      print(f'<EEE>: [dropout]: cant parse <a> tag for Ep. {i}, expect one text node child, but it is of {type(tag.childs[0])!r}')
      sys.exit(1)
    title=tag.childs[0]
    titles.append(title)

  for title, i in zip(titles, range(START_EP, END_EP + 1)):
    old_fn=f'outputs/{i}.txt'
    if title.startswith(f'第{i}話') and title[len(str(i)) + 2].isspace():
      # the title is already formatted and a space is present after the ep. num,
      # dont add it again on our side
      new_fn=f'outputs/{title}.txt'
    else:
      new_fn=f'outputs/{i} {title}.txt'
    print(f'[dropout] renaming file {old_fn!r} --> {new_fn!r}')
    os.rename(old_fn, new_fn)

def main():
  for i in range(START_EP, END_EP + 1):
    out_name=f'outputs/{i}.txt'
    if os.path.exists(out_name):
      continue  # already converted previously, skip
    print(f'[dropout]: reading and processing Ep. {i}')
    fn=f'pages/{i}.html'
    with open(fn, 'r', encoding='utf-8') as f:
      raw=f.read()
      handle(raw, i, out_name)
    print('[dropout]: succeed!')
  print('<+++>: [dropout]: All pages were converted.')

  print('[dropout]: reading and parsing episode list...')
  with open('pages/index.html', 'r', encoding='utf-8') as f:
    raw=f.read()
    rename_main(raw)
  print('<+++>: [dropout]: All Done!')

print(f'[dropout]: script configured for range Ep. {START_EP} to Ep. {END_EP}')
os.makedirs('outputs', exist_ok=True)  # mkdir -p
main()
