# Gemini/Veo Video Generation Demo

This repository contains a small GUI app that uses
[google-generativeai](https://pypi.org/project/google-generativeai/) to generate
videos from prompts.

## Setup

1. Install Python 3 with Tkinter support.
2. Install the dependencies:

```bash
pip install -r requirements.txt
```

3. Obtain an API key for the Gemini/Veo API and set it when running the app or
   paste it in the interface.

## Running

```bash
python app.py
```

Enter your API key, the prompt, configure the video parameters and click
**Generate**. When the generation completes you will be asked where to save the
resulting video file.
