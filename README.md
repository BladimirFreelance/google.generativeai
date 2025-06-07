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
   paste it in the interface. Used keys are saved in `~/.veo_api_keys.db`, an
   SQLite database managed by `db.py`, so they can be selected from a dropdown
   on future runs. Delete this file if you wish to remove saved keys.

## How It Works

The application configures the library with your API key and obtains a client
using `genai.client.get_default_generative_client()`. It then calls
`client.models.generate_videos()` to produce the output clip.
The helper methods in `db.py` manage the stored keys, and the GUI polls the
long‑running operation until a result is ready.

## Running

```bash
python app.py
```

Enter your API key, the prompt, configure the video parameters and click
**Generate**. When the generation completes you will be asked where to save the
resulting video file.

Right‑click or Ctrl‑click any text field to open a context menu for cut,
copy and paste actions.

## Testing

Unit tests require `pytest`. Install it along with the normal dependencies,
then run the test suite using:

```bash
pip install -r requirements.txt pytest
pytest
```

After making changes be sure to re-run the tests to ensure everything still works.
Tests exercise the API wrapper logic without making real network calls.
