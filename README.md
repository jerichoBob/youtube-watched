# youtube-watched

Give a quick sharable summary of the things I've been watching on youtube

## Setup

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Usage

```shell
python3 youtube-watched.py
```
which (with the current mock data) outputs:

```text
Summary of videos watched in the past week:
1. Video ID: abc123
   Summary: A deep dive into the quantum phenomenon of entanglement...
2. Video ID: def456
   Summary: An overview of the latest advancements in AI focusing on transformers...
```