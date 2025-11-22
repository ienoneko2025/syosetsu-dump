#!/bin/bash

#
# data extractor impl for 小説家になろう
#

set -e

dropout_ua='Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0'

dropout_start_ep=1
dropout_end_ep=25
dropout_novel_id=n2165ie

echo "[dropout] script is configured for range Ep. ${dropout_start_ep} to Ep. ${dropout_end_ep}, syosetsu ID ${dropout_novel_id}"

mkdir -p pages

echo "[dropout] entering pages/ dir"
cd pages

[[ -f index.html.complete ]] || {
  echo '[dropout] requesting episode list, description and author info'
  rm -f index.html;
  wget -U "$dropout_ua" --header='Cookie: over18=yes' "https://novel18.syosetu.com/${dropout_novel_id}/" && touch index.html.complete;
  sleep 2;
}

for dropout_ep in $(seq "$dropout_start_ep" "$dropout_end_ep"); do
  # if the flag file exists, skip this episode as it was already downloaded
  [[ -f "${dropout_ep}.complete" ]] || {
    echo "[dropout] requesting Ep. ${dropout_ep}";
    rm -f "${dropout_ep}.html";  # ensure us to get rid of incomplete file
    wget -U "$dropout_ua" --header='Cookie: over18=yes' "https://novel18.syosetu.com/${dropout_novel_id}/${dropout_ep}/" -O "${dropout_ep}.html" && touch "${dropout_ep}.complete";
    sleep 2;  # important, dont overload the remote server
  };
done

echo '[dropout] doing post-clean'
rm *.complete
