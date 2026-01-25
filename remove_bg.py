from rembg import remove
from PIL import Image
import io
import os

input_path = 'logo.png'
output_path = 'logo_sidebar.png'

print(f"Processing {input_path}...")
with open(input_path, 'rb') as i:
    input = i.read()
    output = remove(input)
    
    with open(output_path, 'wb') as o:
        o.write(output)
        
print(f"Saved transparent logo to {output_path}")
