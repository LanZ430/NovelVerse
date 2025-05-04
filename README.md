# NovelVerse
Building a Multi-Modal AI Agent for Immersive Fictional Interaction

## Demo Video
[![Watch the NovelVerse demo video](https://img.youtube.com/vi/E0Y6_lstcI4/maxresdefault.jpg)](https://youtu.be/E0Y6_lstcI4)
*Click the image above to watch the demo video on YouTube*

## Motivation
NovelVerse was born from the desire to transform passive reading experiences into interactive adventures. We believe that stories are more engaging when readers can actively participate as characters within the narrative, making choices that influence their journey through the story world. By leveraging AI technology, we aim to create a new form of entertainment that blends traditional storytelling with interactive elements, allowing readers to experience beloved stories from a first-person perspective.

## Problem Definition
Traditional reading experiences are one-dimensional, with readers acting as passive observers. Even interactive fiction typically offers limited branching paths that restrict creative expression. Additionally, text-only experiences lack visual elements that could enhance immersion. We identified several challenges:

- How to transform static novels into dynamic, interactive experiences
- How to allow readers to assume the identity of any character in a story
- How to generate coherent story continuations based on user choices
- How to maintain narrative consistency while allowing for creative freedom
- How to integrate visual elements that enhance rather than distract from the story

## Solution Approach
NovelVerse addresses these challenges through an agent-based architecture powered by large language models (LLMs) and text-to-image generation. Our approach:

1. **Document Processing**: Automatically parse and structure uploaded novels
2. **Knowledge Extraction**: Identify characters, settings, plots, and key story elements
3. **Role-Playing**: Enable first-person perspective experiences through any character
4. **Multiple Interaction Points**: Provide high-freedom interaction points throughout each chapter
5. **Narrative Consistency**: Intelligently evaluate user choices for story coherence
6. **Visual Enhancement**: Generate images based on scene descriptions
7. **Progress Control**: Allow chapter navigation and progress adjustment

## System Architecture
NovelVerse employs an agent architecture with these key components:

- **AgentCoordinator**: Manages and coordinates all agent activities
- **DocumentAgent**: Processes and pre-processes novel documents
- **KnowledgeAgent**: Extracts characters, settings, and plot elements
- **InteractionAgent**: Handles user-story interactions and narrative generation
- **ImageService**: Provides text-to-image functionality

## Implementation Details

### Technologies Used
- **AI Models**: DeepSeek Chat API for text generation
- **Image Generation**: Jimeng API for text-to-image conversion
- **Frontend**: Streamlit for web interface development
- **Architecture**: Agent-based modular design for extensibility

### Key Features
- **Document Processing**: Upload novel text, automatically process by chapter
- **Character Selection**: Choose any character for first-person experience
- **Immersive Interactions**: Engage with multiple high-freedom interaction points per chapter
- **Story Deviation Assessment**: Smart evaluation of user choices' impact on narrative
- **Text-to-Image Capability**: Generate images based on scene descriptions
- **Progress Control**: Jump between chapters and adjust story progress
- **Web Interface**: User-friendly interactive UI
- **Command Line Support**: Run via command line interface

### Installation

#### Prerequisites
- Python 3.8+
- DeepSeek API key (for LLM)
- Jimeng API credentials (for text-to-image)
  - Access Key ID
  - Secret Access Key

#### Setup Steps
1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables:
```bash
# Linux/Mac
export DEEPSEEK_API_KEY=your_api_key
export IMAGE_ACCESS_KEY_ID=your_access_key_id
export IMAGE_SECRET_KEY=your_secret_access_key

# Windows
set DEEPSEEK_API_KEY=your_api_key
set IMAGE_ACCESS_KEY_ID=your_access_key_id
set IMAGE_SECRET_KEY=your_secret_access_key
```

### Usage

#### Web UI Mode
Start the web UI:
```bash
python -m agent.main ui
```
Then access in browser: http://localhost:8501

#### Command Line Mode
1. Process document:
```bash
python -m agent.main process --file path/to/novel.txt --language zh --percentage 100
```

2. Extract knowledge:
```bash
python -m agent.main knowledge --document document_id
```

3. Begin interaction:
```bash
python -m agent.main interact --document document_id --character character_name
```

## Advanced Features
- **Narrative Deviation Handling**: Warning system for choices that might significantly alter the story
- **First-Person Perspective**: Ensures all content is generated from the selected character's viewpoint
- **Intelligent Progress Evaluation**: Automatically assesses how user choices affect story progression
- **Multiple Image Styles**: Supports various styles including realistic, anime, painting, sketch, and 3D rendering

## Future Development
- **Negative Prompts**: Support for specifying undesired image elements
- **Custom Prompts**: Allow users to manually edit and optimize image prompts
- **Batch Image Generation**: Generate multiple images with different styles at once
- **Image Inpainting**: Support for regenerating specific areas of images
- **Style Consistency**: Ensure consistent style across multiple images in the same story
- **Character Appearance Consistency**: Maintain consistent character appearance across different scenes