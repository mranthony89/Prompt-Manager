import gradio as gr
import json
from prompt_perfezionatore import PromptPerfezionatore

# Inizializza il perfezionatore
perfezionatore = PromptPerfezionatore()

def migliora_e_analizza(prompt_utente):
    """Funzione wrapper per l'integrazione con Gradio."""
    risultati = perfezionatore.migliora_prompt(prompt_utente)
    analisi = perfezionatore.analizza_prompt(prompt_utente)
    return risultati[0], risultati[1], risultati[2], json.dumps(analisi, indent=4, ensure_ascii=False)

# Creazione dell'interfaccia Gradio
app = gr.Interface(
    fn=migliora_e_analizza,
    inputs=gr.Textbox(lines=5, placeholder="Inserisci il prompt da migliorare..."),
    outputs=[
        gr.Textbox(lines=5, label="Prompt Migliorato"),
        gr.Textbox(lines=5, label="Suggerimenti"),
        gr.Textbox(lines=5, label="Spiegazione Modifiche"),
        gr.Textbox(lines=10, label="Analisi Prompt")
    ],
    title="Prompt Perfezionatore",
    description="Inserisci un prompt e ottieni una versione migliorata, suggerimenti e analisi dettagliata."
)

# Questo codice viene eseguito solo quando si esegue lo script direttamente (non quando importato)
if __name__ == "__main__":
    app.launch()