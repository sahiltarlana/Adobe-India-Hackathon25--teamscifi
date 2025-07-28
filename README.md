# Adobe India Hackathon 2025 - Challenge 1a: PDF Processing

## Overview
This solution addresses **Challenge 1a: PDF Processing** of the Adobe India Hackathon 2025. The goal is to extract structured outlines (title and headings: H1, H2, H3 with page numbers) from PDF documents and output them as JSON files. The solution is containerized using Docker, optimized for performance (≤ 10 seconds for 50-page PDFs), and adheres to the challenge constraints (AMD64 architecture, no internet access, ≤ 16 GB RAM, open-source libraries).

## Approach
The solution implements a **hybrid PDF processing system** that combines multiple open-source libraries to achieve high accuracy in heading detection and title extraction. Key features include:

- **Multi-Library Extraction**:
  - **pdfplumber**: Provides precise character positioning and spacing analysis for accurate text block formation.
  - **PyMuPDF**: Enables fast font analysis and structure detection for efficient processing.
- **Cross-Validation**: Combines results from both libraries to validate headings, ensuring high precision and recall.
- **Font Hierarchy Analysis**: Uses percentile-based font size thresholds and bold attributes to classify headings (H1, H2, H3).
- **Regular Expression Patterns**: Identifies common heading formats (e.g., "Chapter 1", "1.1 Section", Roman numerals) for robust detection.
- **Title Extraction**: Selects the largest text on the first page (within constraints) as the document title.
- **Output Format**: Generates JSON files in `/app/output` for each PDF in `/app/input`, conforming to the required schema:
  ```json
  {
    "title": "Document Title",
    "outline": [
      { "level": "H1", "text": "Introduction", "page": 1 },
      { "level": "H2", "text": "Section 1", "page": 2 },
      { "level": "H3", "text": "Subsection", "page": 3 }
    ]
  }
  ```

## Libraries Used
The solution uses the following open-source Python libraries, installed within the Docker container:
- `pdfplumber==0.11.4`: For precise text extraction and positioning.
- `PyMuPDF==1.24.10`: For fast font and structure analysis.
- `pdfminer.six==20231228`: For additional text extraction capabilities (used in the original implementation).
- `numpy==2.1.2`: For efficient percentile calculations in font hierarchy analysis.

## Project Structure
```
Challenge_1a/
├── Dockerfile           # Docker configuration
├── process_pdfs.py      # Main processing script
├── requirements.txt     # Python dependencies
├── README.md            # This documentation
└── sample_dataset/      # Optional, for testing (not submitted)
    ├── pdfs/            # Test PDF files
    ├── outputs/         # Sample JSON outputs
    └── schema/          # Output schema
        └── output_schema.json
```

## How to Build and Run
The solution is containerized for AMD64 architecture and runs offline. Follow these steps to build and run:

1. **Build the Docker Image**:
   ```bash
   docker build --platform linux/amd64 -t pdf-processor .
   ```
   This installs dependencies and sets up the environment.

2. **Run the Container**:
   ```bash
   docker run --rm -v $(pwd)/input:/app/input:ro -v $(pwd)/output:/app/output --network none pdf-processor
   ```
   - Mounts `/app/input` (read-only) for input PDFs.
   - Mounts `/app/output` for JSON outputs.
   - Runs offline (`--network none`).

The script processes all `.pdf` files in `/app/input`, generating `filename.json` for each `filename.pdf` in `/app/output`.

## Performance Optimizations
- **Execution Time**: Optimized for ≤ 10 seconds on 50-page PDFs through efficient text block grouping (`pdfplumber`) and fast font analysis (`PyMuPDF`).
- **Memory Management**: Closes PDF documents after processing to minimize memory usage, staying within 16 GB RAM.
- **Robustness**: Includes error handling to process all PDFs without crashing, logging errors for individual files.
- **Cross-Validation**: Combines `pdfplumber` and `PyMuPDF` to reduce false positives and improve heading detection accuracy.
- **Scalability**: Handles both simple (single-column) and complex (multi-column, tables) PDFs.

## Testing Strategy
- **Simple PDFs**: Tested with single-column documents to ensure basic heading and title extraction.
- **Complex PDFs**: Validated with multi-column layouts, tables, and images to ensure robust parsing.
- **Large PDFs**: Confirmed processing of 50-page PDFs within 10 seconds.
- **Schema Compliance**: JSON outputs validated against `sample_dataset/schema/output_schema.json`.
- **Resource Constraints**: Tested on AMD64 with 8 CPUs and 16 GB RAM, no internet access.

## Notes
- **Multilingual Support**: Not implemented in the current version but can be extended with `pdfminer.six` for languages like Japanese (potential bonus points).
- **Dependencies**: All libraries are open-source, installed via `requirements.txt`, and compatible with AMD64.
- **No Internet Access**: The solution runs offline, with no API or web calls.
- **No GPU Dependencies**: Runs on CPU only, with no ML models (rule-based approach).
- **Error Handling**: Robust try-except blocks ensure processing continues even if individual PDFs fail.

## Limitations and Potential Improvements
- **Multilingual Handling**: Future iterations could add support for non-Latin scripts (e.g., Japanese, Hindi) using `pdfminer.six` or additional libraries.
- **Performance Tuning**: Parallel processing with `multiprocessing` could further reduce execution time for multiple PDFs.
- **Complex Layouts**: Additional logic could improve handling of nested tables or irregular font styles.

## Submission Details
- **GitHub Repository**: Hosted privately at `<your-repository-url>` (to be shared with Adobe evaluators).
- **Submission Deadline**: July 28, 2025, 11:59 PM IST.
- **Docker Compatibility**: Tested with the provided build and run commands:
  ```bash
  docker build --platform linux/amd64 -t pdf-processor .
  docker run --rm -v $(pwd)/input:/app/input:ro -v $(pwd)/output:/app/output --network none pdf-processor
  ```

For any issues or clarifications, please contact the hackathon organizers via the Unstop platform.