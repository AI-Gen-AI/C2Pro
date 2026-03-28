import os

def fix_binary_file(file_path):
    try:
        # Read the raw bytes
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        # Remove null bytes
        clean_data = raw_data.replace(b'\x00', b'')
        
        # Try to decode as UTF-8, replacing errors
        text_content = clean_data.decode('utf-8', errors='replace')
        
        # Write back as clean UTF-8
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
            
        return f"File {file_path} cleaned and rewritten as UTF-8."
    except Exception as e:
        return f"Error fixing file: {str(e)}"

if __name__ == "__main__":
    print(fix_binary_file("C2PRO_MASTER_BACKLOG.md"))
