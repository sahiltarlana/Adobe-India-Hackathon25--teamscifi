import fitz  # PyMuPDF
import os
import json
import time
import torch
import glob
from sentence_transformers import SentenceTransformer, util

# Load the model (will use cache after first download)
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_title_for_page(page_num: int, toc: list) -> str:
    """Finds the section title for a given page number from the ToC."""
    current_title = f"Content from Page {page_num}"
    if not toc:
        return current_title
    for entry in toc:
        if entry[2] <= page_num:
            current_title = entry[1]
        else:
            break
    return current_title

def load_and_chunk_documents(doc_paths: list[str]) -> list[dict]:
    """Loads PDFs and creates chunks using a sliding window of text."""
    # (This function is unchanged)
    print("Step 1: Loading and chunking documents...")
    all_chunks = []
    window_size, overlap = 200, 50
    step_size = window_size - overlap

    for doc_path in doc_paths:
        try:
            with fitz.open(doc_path) as doc:
                toc = doc.get_toc()
                words_with_pages = []
                for page_num, page in enumerate(doc):
                    text = page.get_text("text").strip()
                    page_words = text.split()
                    for word in page_words:
                        words_with_pages.append((word, page_num + 1))

                for i in range(0, len(words_with_pages), step_size):
                    window = words_with_pages[i : i + window_size]
                    if not window: continue
                    
                    chunk_text = " ".join([item[0] for item in window])
                    start_page = window[0][1]
                    section_title = get_title_for_page(start_page, toc)
                    
                    all_chunks.append({
                        "doc_name": os.path.basename(doc_path),
                        "page_number": start_page,
                        "section_title": section_title,
                        "text": chunk_text
                    })
        except Exception as e:
            print(f"Error processing {doc_path}: {e}")
            
    print(f"-> Successfully created {len(all_chunks)} chunks.")
    return all_chunks

def find_relevant_sections(chunks: list[dict], persona: str, job: str) -> dict:
    """
    Finds top chunks for 'subsection_analysis' and summarizes them
    into 'extracted_sections'.
    """
    print("\nStep 2: Performing analysis...")
    query = f"{persona}: {job}"
    
    query_embedding = model.encode(query, convert_to_tensor=True)
    chunk_texts = [chunk['text'] for chunk in chunks]
    chunk_embeddings = model.encode(chunk_texts, convert_to_tensor=True)
    
    cosine_scores = util.cos_sim(query_embedding, chunk_embeddings)
    # Get more results to populate both lists, e.g., top 10 chunks
    top_results = torch.topk(cosine_scores, k=min(10, len(chunks)), dim=-1)
    
    # --- Create the 'subsection_analysis' list from the top chunks ---
    subsection_analysis = []
    top_chunks = []
    for score, idx in zip(top_results.values[0], top_results.indices[0]):
        chunk = chunks[idx]
        subsection_analysis.append({
            "document": chunk["doc_name"],
            "refined_text": chunk["text"],
            "page_number": chunk["page_number"]
        })
        top_chunks.append(chunk)

    # --- Create the 'extracted_sections' list by summarizing the top chunks ---
    extracted_sections = []
    processed_sections = set()
    rank = 1
    for chunk in top_chunks:
        section_key = (chunk['doc_name'], chunk['section_title'])
        if section_key not in processed_sections:
            extracted_sections.append({
                "document": chunk["doc_name"],
                "section_title": chunk["section_title"],
                "importance_rank": rank,
                "page_number": chunk["page_number"]
            })
            processed_sections.add(section_key)
            rank += 1
            if rank > 5: # Limit to top 5 unique sections
                break

    return {
        "extracted_sections": extracted_sections,
        "subsection_analysis": subsection_analysis
    }

def format_output_json(results: dict, inputs: dict, processing_time: float) -> str:
    """
    Formats the final results into the required JSON structure with three keys.
    """
    print("\nStep 3: Formatting final JSON output...")
    output = {
        "metadata": {
            "input_documents": [os.path.basename(p) for p in inputs["doc_paths"]],
            "persona": inputs["persona"],
            "job_to_be_done": inputs["job"],
            "processing_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        # Add the two analysis keys as per the new format
        "extracted_sections": results["extracted_sections"],
        "subsection_analysis": results["subsection_analysis"]
    }
    return json.dumps(output, indent=4)

def main():
    """Main function to run the pipeline by reading from the input directory."""
    # (This function is unchanged)
    base_path = "./Collection 2" #change this location for each testing location
    input_json_path = os.path.join(base_path, "challenge1b_input.json")
    pdf_directory = os.path.join(base_path, "PDFs")

    try:
        with open(input_json_path, 'r') as f:
            input_data = json.load(f)
        persona = input_data["persona"]["role"]
        job = input_data["job_to_be_done"]["task"]
    except Exception as e:
        print(f"Error reading input JSON: {e}")
        return

    doc_paths = glob.glob(os.path.join(pdf_directory, "*.pdf"))
    if not doc_paths:
        print(f"Error: No PDF files found in '{pdf_directory}'.")
        return
    
    inputs = {"doc_paths": doc_paths, "persona": persona, "job": job}
    
    start_time = time.time()
    
    document_chunks = load_and_chunk_documents(inputs["doc_paths"])
    if not document_chunks:
        print("No text could be extracted. Exiting.")
        return

    analysis_results = find_relevant_sections(document_chunks, inputs["persona"], inputs["job"])
    end_time = time.time()
    
    final_json = format_output_json(analysis_results, inputs, end_time - start_time)

    print("\n--- FINAL OUTPUT ---")
    print(final_json)

    with open(os.path.join(base_path, "challenge1b_output.json"), "w") as f:
        f.write(final_json)
    print("\nOutput saved to challenge1b_output.json")

if __name__ == "__main__":
    main()