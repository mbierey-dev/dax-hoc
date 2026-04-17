from IPython.display import display, Markdown

def display_formatted_cell(df, row_num, col_name):
    """
    Extracts text from a specific DataFrame cell, formats hidden markdown 
    bullet points, and renders it as native Markdown in Jupyter.
    """
    try:
        # Extract the text and ensure it is treated as a string
        raw_text = str(df.loc[row_num, col_name])
        
        # Replace the hyphen separators with a newline and a bullet point
        formatted_text = raw_text.replace(' - **', '\n* **')
        
        # Ensure the very first item also gets a bullet point
        if formatted_text.startswith('**'):
            formatted_text = '* ' + formatted_text
            
        # Command Jupyter to render the string as Markdown
        display(Markdown(formatted_text))
        
    except KeyError:
        print(f"Error: Row {row_num} or Column '{col_name}' could not be found in the DataFrame.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")