import re
import os

def clean_markdown(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 1. Remove control characters except newline and tab
        # This fixes the strange symbols like SOH ()
        clean_content = "".join(ch for ch in content if ch >= " " or ch in "\n\t")
        
        # 2. Fix broken encoding artifacts (e.g., producci%n -> producción)
        # Attempt to recover common Spanish characters if they were mangled
        clean_content = clean_content.replace("producci%n", "producción")
        clean_content = clean_content.replace("versi%n", "versión")
        clean_content = clean_content.replace("m%tricas", "métricas")
        clean_content = clean_content.replace("par%metro", "parámetro")
        clean_content = clean_content.replace("categor%a", "categoría")
        
        # 3. MD012: No multiple blank lines (keep at most one)
        clean_content = re.sub(r'\n{3,}', '\n\n', clean_content)
        
        # 4. MD009: No trailing spaces
        lines = [line.rstrip() for line in clean_content.split('\n')]
        
        # 5. Ensure tables have proper spacing (optional but good for readability)
        # We'll keep it simple to avoid breaking table structure
        
        final_content = '\n'.join(lines)
        
        # 6. Ensure exactly one newline at the end of the file
        final_content = final_content.strip() + '\n'
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        return "Markdown file cleaned successfully."
    except Exception as e:
        return f"Error cleaning file: {str(e)}"

if __name__ == "__main__":
    print(clean_markdown("C2PRO_MASTER_BACKLOG.md"))
