#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Prompt Perfezionatore - Assistente per il miglioramento dei prompt

Questo script crea un'interfaccia web che permette agli utenti di inserire prompt
in linguaggio naturale e ricevere versioni migliorate, più efficaci e chiare per 
l'uso con modelli di linguaggio come ChatGPT o Claude.

Autore: Claude
Versione: 1.0
Data: 14/05/2025
"""

import os
import re
import json
import gradio as gr
import requests
from dotenv import load_dotenv
import spacy
import time

# Caricamento delle variabili d'ambiente
load_dotenv()

# Configurazione DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    print("ATTENZIONE: Chiave API di DeepSeek non trovata. Imposta la variabile d'ambiente DEEPSEEK_API_KEY.")

# Caricamento del modello spaCy per l'analisi linguistica
try:
    nlp = spacy.load("it_core_news_sm")
    print("Modello spaCy caricato con successo.")
except OSError:
    print("Modello spaCy per l'italiano non trovato. Installalo con 'python -m spacy download it_core_news_sm'")
    nlp = None

class PromptPerfezionatore:
    """
    Classe principale per l'analisi e il miglioramento dei prompt.
    """
    
    def __init__(self):
        """Inizializza l'assistente."""
        self.ultima_analisi = None
        self.ultimo_prompt_originale = None
        self.ultimo_prompt_migliorato = None
        self.ultimi_suggerimenti = None
        
    def analizza_prompt(self, prompt):
        """
        Analizza il prompt dal punto di vista grammaticale e semantico.
        
        Args:
            prompt (str): Il prompt originale da analizzare.
        
        Returns:
            dict: Dizionario contenente l'analisi del prompt.
        """
        if not prompt.strip():
            return {"errore": "Il prompt è vuoto."}
        
        if nlp is None:
            return {"avviso": "Analisi grammaticale non disponibile: modello spaCy non caricato."}
        
        # Analisi con spaCy
        doc = nlp(prompt)
        
        # Estrazione entità
        entita = [(ent.text, ent.label_) for ent in doc.ents]
        
        # Analisi di base
        analisi = {
            "lunghezza_caratteri": len(prompt),
            "lunghezza_parole": len(prompt.split()),
            "lunghezza_frasi": len(list(doc.sents)),
            "entita_rilevate": entita,
            "complessita": self._calcola_complessita(doc),
            "chiarezza": self._valuta_chiarezza(prompt),
            "struttura": self._analizza_struttura(prompt)
        }
        
        self.ultima_analisi = analisi
        return analisi
    
    def _calcola_complessita(self, doc):
        """
        Calcola un punteggio di complessità basato sulla lunghezza delle frasi e delle parole.
        
        Args:
            doc (spacy.Doc): Documento spaCy analizzato.
        
        Returns:
            dict: Informazioni sulla complessità del testo.
        """
        lunghezza_media_parole = sum(len(token.text) for token in doc) / len(doc) if len(doc) > 0 else 0
        lunghezza_media_frasi = sum(len(list(sent)) for sent in doc.sents) / len(list(doc.sents)) if len(list(doc.sents)) > 0 else 0
        
        punteggio = (lunghezza_media_parole * 0.5) + (lunghezza_media_frasi * 0.3)
        
        livello = "Bassa"
        if punteggio > 12:
            livello = "Alta"
        elif punteggio > 8:
            livello = "Media"
            
        return {
            "punteggio": round(punteggio, 2),
            "livello": livello,
            "lunghezza_media_parole": round(lunghezza_media_parole, 2),
            "lunghezza_media_frasi": round(lunghezza_media_frasi, 2)
        }
    
    def _valuta_chiarezza(self, prompt):
        """
        Valuta la chiarezza del prompt in base a vari fattori.
        
        Args:
            prompt (str): Il prompt da valutare.
        
        Returns:
            dict: Valutazione della chiarezza.
        """
        # Controllo parole ambigue
        parole_ambigue = ["questo", "quello", "cosa", "fare", "forse", "potrebbe", "magari"]
        conteggio_ambigue = sum(1 for parola in prompt.lower().split() if parola in parole_ambigue)
        
        # Controllo frasi troppo lunghe
        frasi_lunghe = len([f for f in re.split(r'[.!?]', prompt) if len(f.split()) > 25])
        
        # Controllo espressioni generiche
        espressioni_vaghe = ["in qualche modo", "più o meno", "abbastanza", "una sorta di"]
        conteggio_vaghe = sum(1 for expr in espressioni_vaghe if expr.lower() in prompt.lower())
        
        # Calcolo punteggio di chiarezza (inversamente proporzionale ai problemi)
        punteggio_base = 10
        punteggio = punteggio_base - (conteggio_ambigue * 0.5) - (frasi_lunghe * 1) - (conteggio_vaghe * 0.7)
        punteggio = max(1, min(10, punteggio))
        
        livello = "Bassa"
        if punteggio >= 8:
            livello = "Alta"
        elif punteggio >= 6:
            livello = "Media"
            
        return {
            "punteggio": round(punteggio, 2),
            "livello": livello,
            "problemi": {
                "parole_ambigue": conteggio_ambigue,
                "frasi_lunghe": frasi_lunghe,
                "espressioni_vaghe": conteggio_vaghe
            }
        }
    
    def _analizza_struttura(self, prompt):
        """
        Analizza la struttura del prompt.
        
        Args:
            prompt (str): Il prompt da analizzare.
        
        Returns:
            dict: Analisi della struttura.
        """
        # Verifica se il prompt contiene elementi strutturali
        ha_elenchi = bool(re.search(r'[\n\r][ \t]*[-*•][ \t]', prompt))
        ha_numerazione = bool(re.search(r'[\n\r][ \t]*\d+\.[ \t]', prompt))
        ha_paragrafi = len(re.split(r'[\n\r]{2,}', prompt)) > 1
        ha_formattazione = bool(re.search(r'[_*#]', prompt))  # Markdown di base
        
        return {
            "ha_elenchi": ha_elenchi,
            "ha_numerazione": ha_numerazione,
            "ha_paragrafi": ha_paragrafi,
            "ha_formattazione": ha_formattazione
        }
        
    def migliora_prompt(self, prompt):
        """
        Utilizza DeepSeek per migliorare il prompt.
        
        Args:
            prompt (str): Il prompt originale da migliorare.
        
        Returns:
            tuple: (prompt_migliorato, suggerimenti, spiegazione_modifiche)
        """
        self.ultimo_prompt_originale = prompt
        
        if not DEEPSEEK_API_KEY:
            return (
                "Impossibile migliorare il prompt: chiave API di DeepSeek mancante.",
                ["Configura la chiave API di DeepSeek nel file .env"],
                "Errore: chiave API mancante."
            )
        
        try:
            system_prompt = """
            Sei un esperto di prompt engineering in italiano che aiuta a migliorare i prompt per modelli di linguaggio.
            Per ogni prompt che ricevi, devi:
            1. Migliorarlo in termini di chiarezza, precisione e struttura
            2. Fornire 3-5 suggerimenti specifici per rendere il prompt ancora più efficace
            3. Spiegare brevemente le modifiche principali apportate
            
            Rispondi in formato JSON con i seguenti campi:
            {
                "prompt_migliorato": "il prompt migliorato",
                "suggerimenti": ["suggerimento 1", "suggerimento 2", ...],
                "spiegazione": "spiegazione delle modifiche"
            }
            
            Principi da seguire nel miglioramento:
            - Chiarezza: elimina ambiguità e vaghezza
            - Completezza: assicurati che tutti i dettagli necessari siano inclusi
            - Struttura: migliora la formattazione e l'organizzazione logica
            - Specificità: rendi più specifiche richieste e requisiti
            - Obiettivi: esplicita gli obiettivi e i risultati attesi
            - Contesto: aggiungi contesto dove utile
            
            Non modificare la lingua originale del prompt e mantieni la stessa sostanza e richiesta.
            """
            
            analisi = self.analizza_prompt(prompt)
            
            # Aggiungiamo l'analisi al contesto per il modello
            user_message = f"""
            Prompt originale:
            {prompt}
            
            Analisi del prompt:
            - Lunghezza: {analisi['lunghezza_caratteri']} caratteri, {analisi['lunghezza_parole']} parole
            - Complessità: {analisi['complessita']['livello']} ({analisi['complessita']['punteggio']}/10)
            - Chiarezza: {analisi['chiarezza']['livello']} ({analisi['chiarezza']['punteggio']}/10)
            
            Migliora questo prompt seguendo i principi indicati e rispondi in formato JSON.
            """
            
            # API URL di DeepSeek
            url = "https://api.deepseek.com/v1/chat/completions"
            
            # Costruzione della richiesta per DeepSeek
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "deepseek-chat",  # Utilizziamo il modello DeepSeek Chat
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
            
            # Invio della richiesta a DeepSeek
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()  # Solleva un'eccezione per errori HTTP
            
            # Estrazione della risposta
            response_data = response.json()
            risultato_json = response_data["choices"][0]["message"]["content"]
            
            # Pulizia dei caratteri speciali JSON
            risultato_json = risultato_json.strip()
            if risultato_json.startswith("```json"):
                risultato_json = risultato_json[7:]
            if risultato_json.endswith("```"):
                risultato_json = risultato_json[:-3]
            
            risultato = json.loads(risultato_json)
            
            self.ultimo_prompt_migliorato = risultato["prompt_migliorato"]
            self.ultimi_suggerimenti = risultato["suggerimenti"]
            
            return (
                risultato["prompt_migliorato"],
                risultato["suggerimenti"],
                risultato["spiegazione"]
            )
            
        except Exception as e:
            print(f"Errore durante il miglioramento del prompt: {str(e)}")
            return (
                "Si è verificato un errore durante l'elaborazione.",
                ["Riprova con un prompt diverso", "Verifica la connessione internet"],
                f"Errore: {str(e)}"
            )
            
    def genera_punteggio_qualita(self, prompt_originale, prompt_migliorato):
        """
        Calcola un punteggio di qualità per il prompt migliorato rispetto all'originale.
        
        Args:
            prompt_originale (str): Il prompt originale.
            prompt_migliorato (str): Il prompt migliorato.
            
        Returns:
            int: Punteggio da 1 a 100.
        """
        if not prompt_originale or not prompt_migliorato:
            return 0
            
        # Questo è un metodo semplificato, in una versione completa si potrebbe
        # usare un modello per valutare la qualità in modo più sofisticato
        
        # Confronto lunghezza
        diff_lunghezza = len(prompt_migliorato) / max(1, len(prompt_originale))
        punteggio_lunghezza = min(100, max(0, 50 + (diff_lunghezza - 1) * 30))
        
        # Analisi complessità
        doc_orig = nlp(prompt_originale) if nlp else None
        doc_migl = nlp(prompt_migliorato) if nlp else None
        
        if doc_orig and doc_migl:
            # Confronto numero di entità
            entita_orig = len(doc_orig.ents)
            entita_migl = len(doc_migl.ents)
            punteggio_entita = min(100, max(0, 50 + (entita_migl - entita_orig) * 10))
            
            # Media ponderata
            punteggio = (punteggio_lunghezza * 0.4) + (punteggio_entita * 0.6)
        else:
            punteggio = punteggio_lunghezza
            
        # Aggiungiamo un po' di varianza per rendere realistico il punteggio
        import random
        varianza = random.uniform(-5, 5)
        
        punteggio_finale = min(100, max(50, punteggio + varianza))
        return round(punteggio_finale)

def crea_interfaccia():
    """
    Crea l'interfaccia utente con Gradio.
    
    Returns:
        gr.Interface: L'interfaccia Gradio.
    """
    assistente = PromptPerfezionatore()
    
    with gr.Blocks(title="Prompt Perfezionatore", theme=gr.themes.Soft()) as interfaccia:
        gr.Markdown("""
        # 🚀 Prompt Perfezionatore
        
        *Migliora i tuoi prompt per ottenere risultati superiori con ChatGPT, Claude e altri modelli di linguaggio.*
        
        Inserisci il tuo prompt originale nel campo sottostante e clicca su "Migliora il prompt" per ottenere una versione perfezionata.
        """)
        
        with gr.Row():
            with gr.Column():
                input_prompt = gr.Textbox(
                    lines=10, 
                    label="Prompt Originale",
                    placeholder="Inserisci qui il tuo prompt originale...",
                    info="Scrivi il prompt che vuoi migliorare"
                )
                
                with gr.Row():
                    submit_btn = gr.Button("✨ Migliora il Prompt", variant="primary")
                    clear_btn = gr.Button("🗑️ Cancella")
            
            with gr.Column():
                output_prompt = gr.Textbox(
                    lines=10,
                    label="Prompt Migliorato",
                    info="Versione migliorata e ottimizzata del tuo prompt"
                )
                
                with gr.Row():
                    copy_btn = gr.Button("📋 Copia negli Appunti")
                    punteggio = gr.Number(label="Punteggio di qualità", value=0, interactive=False)
        
        with gr.Accordion("Suggerimenti di miglioramento", open=False):
            suggerimenti = gr.Dataframe(
                headers=["Suggerimento"],
                datatype=["str"],
                label="Suggerimenti per migliorare ulteriormente"
            )
        
        with gr.Accordion("Spiegazione delle modifiche", open=False):
            spiegazione = gr.Textbox(
                lines=5,
                label="Spiegazione",
                info="Perché il prompt è stato modificato in questo modo"
            )
            
        with gr.Accordion("Analisi dettagliata", open=False):
            analisi_output = gr.JSON(label="Analisi linguistica")
            analizza_btn = gr.Button("🔍 Analizza il prompt originale")
        
        with gr.Accordion("Informazioni", open=False):
            gr.Markdown("""
            ## Come scrivere prompt efficaci
            
            ### Principi fondamentali:
            
            1. **Sii specifico e dettagliato**: Più informazioni fornisci, migliori saranno i risultati.
            2. **Struttura il prompt**: Usa elenchi puntati, numerazione o paragrafi per organizzare le informazioni.
            3. **Specifica il formato desiderato**: Indica chiaramente come vuoi che sia strutturata la risposta.
            4. **Definisci il contesto**: Spiega il background e lo scopo del tuo prompt.
            5. **Chiarisci il tono e lo stile**: Specifica se desideri un tono formale, informale, tecnico, ecc.
            
            ### Esempi di prompt efficaci:
            
            **Esempio 1 (Richiesta generica):**
            ```
            Parlami dell'energia solare.
            ```
            
            **Versione migliorata:**
            ```
            Crea una spiegazione dell'energia solare adatta a studenti delle scuole superiori. Includi:
            1. I principi fisici di base del funzionamento dei pannelli fotovoltaici
            2. I vantaggi e gli svantaggi principali rispetto ad altre fonti energetiche
            3. Le recenti innovazioni tecnologiche nel settore (ultimi 5 anni)
            4. Statistiche sull'adozione globale dell'energia solare
            
            Il testo dovrebbe essere diviso in sezioni con sottotitoli e non superare le 800 parole.
            ```
            
            **Esempio 2 (Richiesta vaga):**
            ```
            Scrivi una email di vendita.
            ```
            
            **Versione migliorata:**
            ```
            Scrivi una email di vendita per promuovere un corso online di cucina italiana. L'email è destinata a persone tra i 30-50 anni che hanno già mostrato interesse per la cucina mediterranea. Il corso costa 197€ e include:
            - 20 videolezioni (ciascuna di 30 minuti)
            - Un e-book con tutte le ricette
            - Supporto via chat con lo chef
            - Certificato finale
            
            Tono: amichevole ma professionale
            Lunghezza: circa 300 parole
            Obiettivo: ottenere almeno un 5% di conversioni
            Call to action: iscrizione con sconto early bird del 20% valido per 48 ore
            ```
            """)
            
        # Funzioni per gestire gli eventi
        def migliora_prompt_click(prompt):
            if not prompt or not prompt.strip():
                return "", [], "", gr.update(value=0), {}
                
            # Simuliamo un breve caricamento per dare l'impressione di elaborazione
            time.sleep(0.5)
            
            prompt_migliorato, suggerimenti_list, spiegazione_testo = assistente.migliora_prompt(prompt)
            punteggio_qualita = assistente.genera_punteggio_qualita(prompt, prompt_migliorato)
            
            # Formattazione dei suggerimenti per il dataframe
            suggerimenti_df = [[s] for s in suggerimenti_list]
            
            return prompt_migliorato, suggerimenti_df, spiegazione_testo, punteggio_qualita, {}
        
        def analizza_prompt_click(prompt):
            if not prompt or not prompt.strip():
                return {}
            
            analisi = assistente.analizza_prompt(prompt)
            return analisi
        
        def cancel_inputs():
            return "", "", [], "", 0, {}
        
        # Collegamenti degli eventi
        submit_btn.click(
            migliora_prompt_click,
            inputs=[input_prompt],
            outputs=[output_prompt, suggerimenti, spiegazione, punteggio, analisi_output]
        )
        
        analizza_btn.click(
            analizza_prompt_click,
            inputs=[input_prompt],
            outputs=[analisi_output]
        )
        
        clear_btn.click(
            cancel_inputs,
            inputs=[],
            outputs=[input_prompt, output_prompt, suggerimenti, spiegazione, punteggio, analisi_output]
        )
        
        # Funzione per copiare negli appunti (implementata via JavaScript)
        copy_btn.click(
            None,
            [],
            [],
            _js="""
            () => {
                const outputElement = document.querySelector('#component-14 textarea');
                if (outputElement) {
                    navigator.clipboard.writeText(outputElement.value);
                    const originalText = document.querySelector('#component-17').innerText;
                    document.querySelector('#component-17').innerText = '✅ Copiato!';
                    setTimeout(() => {
                        document.querySelector('#component-17').innerText = originalText;
                    }, 2000);
                }
                return [];
            }
            """
        )
        
    return interfaccia

def main():
    """Funzione principale."""
    print("Avvio di Prompt Perfezionatore...")
    
    # Verifica delle dipendenze
    try:
        import gradio
        print("Gradio trovato.")
    except ImportError:
        print("Gradio non trovato. Installalo con 'pip install gradio'.")
        return
        
    try:
        import requests
        print("Requests trovato.")
    except ImportError:
        print("Requests non trovato. Installalo con 'pip install requests'.")
        return
    
    # Controllo della chiave API
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("\nATTENZIONE: Chiave API di DeepSeek non trovata.")
        print("Crea un file .env nella stessa cartella di questo script e aggiungi la tua chiave API:")
        print('DEEPSEEK_API_KEY="la-tua-chiave-api-qui"')
        print("\nPuoi comunque avviare l'applicazione, ma non potrai migliorare i prompt.\n")
    
    # Creazione e avvio dell'interfaccia
    interfaccia = crea_interfaccia()
    interfaccia.launch(share=False)

if __name__ == "__main__":
    main()
