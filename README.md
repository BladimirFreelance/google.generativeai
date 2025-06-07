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
   paste it in the interface. Used keys are saved in `~/.veo_api_keys.db` so
   they can be selected from a dropdown on future runs.

## Running

```bash
python app.py
```

Enter your API key, the prompt, configure the video parameters and click
**Generate**. When the generation completes you will be asked where to save the
resulting video file.

Advanced settings are available under **Advanced Options** and map to fields on
`GenerateVideosConfig`:

- **FPS** – frames per second for the output video.
- **Aspect Ratio** – choose 16:9 or 9:16.
- **Seed** – fixed seed for reproducible results.
- **Negative Prompt** – specify concepts to avoid.
- **Generate Audio** – include audio in the generated clip.

## Testing

Unit tests require `pytest`. Install it along with the normal dependencies and
run the test suite with:

```bash
pip install -r requirements.txt pytest
pytest
```

Tests exercise the API wrapper logic without making real network calls.
