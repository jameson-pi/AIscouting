from pypdf import PdfReader

def extract_text_from_pdf(pdf_path, txt_path):
    try:
        reader = PdfReader(pdf_path)
        with open(txt_path, "w", encoding="utf-8") as f:
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    f.write(text)
                    f.write("\n\n")
        print(f"Successfully extracted text to {txt_path}")
    except Exception as e:
        print(f"Error extracting text: {e}")

if __name__ == "__main__":
    extract_text_from_pdf("2025GameManual.pdf", "game_rules.txt")
