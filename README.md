![alt text](https://github.com/aomukai/Writingway/blob/main/assets/logo.png?raw=true "Logo")

> # What is Writingway: An AI-Powered Creative Writing Companion

Writingway is an innovative AI-powered creative writing tool designed to empower authors throughout their writing process, from initial brainstorming to final polishing.  It offers a comprehensive suite of features to help writers refine their prose, analyze story structure, and dynamically manage contextual elements within their narratives.

## Key Features

- **Interactive Chat-Based Workshop:** Engage in dynamic, real-time collaboration with the AI through a chat interface.  Brainstorm ideas, explore different narrative paths, and receive instant feedback on your writing.  This interactive environment fosters creativity and helps overcome writer's block.

- **Customizable Prompts:** Tailor the AI's assistance to your specific needs with customizable prompts.  Whether you're struggling with character development, plot progression, or world-building, Writingway allows you to fine-tune the AI's focus to generate relevant and inspiring suggestions.

- **Project Structure View:** Maintain a clear overview of your project's organization with a dedicated project structure view.  Visualize your chapters, scenes, and character arcs to ensure narrative coherence and identify areas for improvement.  This feature promotes organized writing and facilitates complex story management.

- **Dynamic Contextual Compendium:**  Keep track of intricate world-building details, character backstories, and plot points in a centralized compendium.  Writingway dynamically integrates this information, ensuring consistency and enriching the depth of your narrative.  This feature eliminates the need for cumbersome note-keeping and allows for seamless context management.

## Getting Started

This section provides a step-by-step guide on how to install and run Writingway.  Even if you're new to Python, these instructions should help you get started.

**Prerequisites:**

Python 3.11 is recommended. Python 3.12 and 3.13 are also supported. The setup scripts will attempt to detect a compatible Python version automatically.

**4. Install Writingway (Placeholder):**

Windows users:
Run setup_writingway.bat

Mac OS users:
Mac OS requires an audio tool that is not available for install by the Writingway setup script. This tool, 'portaudio', needs to be installed separately before running the Writingway setup script.
1. Install Homebrew for Mac OS if you haven't already
2. Run this command: 'brew install portaudio'

Mac OS/Linux users:
Execute this command in a terminal window from the Writingway root directory

bash setup_writingway.sh

**5. Run Writingway:**

Windows users:
Double click on the start.bat file to run the program. You can also right click and select Create Shortcut, then move the shortcut to your desktop.

Mac OS/Linux users:
Execute this command in a terminal window from the Writingway root directory
source start.sh

**Troubleshooting:**

- If you encounter any errors during installation, make sure you have a stable internet connection.
- If `pip` is not recognized, ensure that Python's Scripts directory is added to your system's PATH environment variable. (This is usually done automatically during Python installation if you checked the "Add Python to PATH" option.)
- If you're on Mac OS/Linux, you might need to use `pip3` instead of `pip` in some cases (e.g., `pip3 install PyQt5 pyttsx3 requests`).
- On Linux, you may need to install `python3-dev` (or `python3.11-dev`) and `portaudio19-dev` packages for pyaudio to build successfully.

If you still have trouble, please consult the project's issue tracker or support channels for assistance.

```

**Key improvements for beginners:**

*   **Step-by-step instructions:**  Breaks down the installation process into manageable steps.
*   **Clear explanations:** Explains the purpose of each step and the libraries being installed.
*   **Platform-specific instructions:** Provides instructions for Windows, macOS, and Linux.
*   **Verification step:**  Shows how to verify that Python is installed correctly.
*   **Troubleshooting tips:** Offers some common solutions to potential problems.
*   **Placeholder for Writingway installation and running:**  Clearly indicates where to put the specific instructions for your project.

```

## Contributing

Contributions are welcome! Please submit pull requests for bug fixes, new features, or improvements to the documentation. For larger changes, it's recommended to open an issue first to discuss the proposed changes.

## License

This project is licensed under the MIT License.

## Acknowledgements

This project utilizes the following libraries:

- faiss-cpu


- langchain
- langchain-core
- langchain-openai
- langchain-anthropic
- langchain-google-genai
- langchain-ollama
- langchain-community
- numpy
- pydantic
- PyQt5
- PyQtChart
- pyttsx3
- requests
- spacy
- textstat
- tiktoken
- BeautifulSoup4
- wikipediaapi

## Contact

For any questions or support, please post to the issues or discussions page on github project page, or join our Discord server: <https://discord.gg/xkkGaRFXNX>
