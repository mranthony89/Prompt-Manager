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
        
        try:    
            # Analisi dei prompt
            if nlp:
                doc_orig = nlp(prompt_originale)
                doc_migl = nlp(prompt_migliorato)
                
                # Calcolo metriche originali
                analisi_orig = self.analizza_prompt(prompt_    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException)
    )
    def _chiama_api_deepseek(self, system_prompt, user_message, model="deepseek-chat", temperatura=0.7):
        """
        Chiama l'API DeepSeek con gestione degli errori migliorata.
        
        Args:
            system_prompt (str): Il prompt di sistema.
            user_message (str): Il messaggio dell'utente.
            model (str): Il modello da utilizzare.
            temperatura (float): La temperatura per la generazione.
            
        Returns:
            dict: La risposta dell'API.
            
        Raises:
            requests.exceptions.RequestException: Se la richiesta all'API fallisce dopo i tentativi.
        """
        url = "https://api.deepseek.com/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperatura,
            "max_tokens": 2000
        }
        
        self.logger.info(f"Invio richiesta a DeepSeek API. Model: {model}, Content length: {len(user_message)}")
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            self.logger.info("Risposta ricevuta correttamente dall'API")
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                self.logger.warning("Rate limit raggiunto. Attesa prima di riprovare...")
            elif e.response.status_code == 401:
                self.logger.error("Errore di autenticazione API. Verifica la chiave API.")
                # Non ritentiamo per errori di autenticazione
                raise
            self.logger.error(f"HTTP error: {str(e)}")
            raise
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Errore di connessione: {str(e)}")
            raise
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout della richiesta: {str(e)}")
            raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Errore API: {str(e)}")
            raise    def _calcola_leggibilita(self, testo, doc):
        """
        Calcola indici di leggibilità per il testo italiano.
        
        Args:
            testo (str): Il testo da analizzare.
            doc (spacy.Doc): Il documento spaCy già analizzato.
            
        Returns:
            dict: Dizionario contenente indici di leggibilità.
        """
        # Calcolo indice Gulpease (specifico per l'italiano)
        # Formula: 89 + (300 * numero_frasi - 10 * numero_lettere) / numero_parole
        
        num_frasi = len(list(doc.sents))
        num_parole = len([token for token in doc if not token.is_punct and not token.is_space])
        num_lettere = sum(len(token.text) for token in doc if not token.is_punct and not token.is_space)
        
        if num_parole == 0:
            gulpease = 0
        else:
            gulpease = 89 + (300 * num_frasi - 10 * num_lettere) / num_parole
            gulpease = max(0, min(100, gulpease))  # Limitare a 0-100
        
        # Interpretazione gulpease
        difficolta = "Molto difficile"
        if gulpease > 80:
            difficolta = "Molto facile"
        elif gulpease > 60:
            difficolta = "Facile"
        elif gulpease > 40:
            difficolta = "Media"
        
        return {
            "gulpease": round(gulpease, 2),
            "difficolta": difficolta,
            "statistiche": {
                "frasi": num_frasi,
                "parole": num_parole,
                "lettere": num_lettere
            }
        }#!/usr/bin/env python3
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
import logging
import hashlib
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from logging.handlers import RotatingFileHandler
import html
from typing import Dict, List, Any, Optional, Union

# Configurazione del logging
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler('prompt_perfezionatore.log', maxBytes=5*1024*1024, backupCount=2),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# Inizializzazione del logger
logger = setup_logging()

# Caricamento delle variabili d'ambiente
load_dotenv()

# Configurazione DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    logger.warning("Chiave API di DeepSeek non trovata. Imposta la variabile d'ambiente DEEPSEEK_API_KEY.")

# Caricamento del modello spaCy per l'analisi linguistica
try:
    nlp = spacy.load("it_core_news_sm")
    logger.info("Modello spaCy caricato con successo.")
except OSError:
    logger.error("Modello spaCy per l'italiano non trovato. Installalo con 'python -m spacy download it_core_news_sm'")
    nlp = None

class GrammarChecker:
    """
    Classe per la verifica grammaticale avanzata utilizzando l'API di LanguageTool.
    """
    
    def __init__(self):
        """Inizializza il verificatore grammaticale."""
        self.api_url = "https://languagetool.org/api/v2/check"
        self.logger = logging.getLogger(__name__)
        self.ultimo_controllo = None
        self.ultima_risposta = None
        self.servizio_disponibile = True
        
    def verifica_testo(self, testo: str, lingua: str = "it") -> Dict[str, Any]:
        """
        Verifica la grammatica di un testo utilizzando LanguageTool.
        
        Args:
            testo (str): Il testo da verificare.
            lingua (str, optional): Il codice della lingua. Default: "it".
            
        Returns:
            dict: Risultato dell'analisi grammaticale o dizionario vuoto in caso di errore.
        """
        # Se il servizio è stato contrassegnato come non disponibile, evita la chiamata API
        if not self.servizio_disponibile:
            self.logger.warning("Servizio LanguageTool non disponibile, verifica saltata")
            return {
                "errori": [],
                "servizio_disponibile": False,
                "messaggio": "Servizio LanguageTool non disponibile. Riprova più tardi."
            }
            
        # Limita la lunghezza del testo per evitare problemi con l'API
        testo = testo[:5000] if len(testo) > 5000 else testo
        
        # Parametri per la richiesta
        params = {
            "text": testo,
            "language": lingua,
            "enabledOnly": "false"
        }
        
        try:
            self.logger.info(f"Invio richiesta a LanguageTool API. Lunghezza testo: {len(testo)}")
            
            # Invio della richiesta con timeout
            response = requests.post(self.api_url, data=params, timeout=10)
            
            # Controllo risposta
            if response.status_code == 200:
                self.ultima_risposta = response.json()
                self.ultimo_controllo = time.time()
                self.servizio_disponibile = True
                
                # Elaborazione dei risultati
                matches = self.ultima_risposta.get("matches", [])
                
                # Conteggio errori per categoria
                errori_per_categoria = {}
                for match in matches:
                    categoria = match.get("rule", {}).get("category", {}).get("name", "Altro")
                    if categoria not in errori_per_categoria:
                        errori_per_categoria[categoria] = 0
                    errori_per_categoria[categoria] += 1
                
                # Creazione delle regole violate
                regole_violate = []
                for match in matches:
                    regola = {
                        "messaggio": match.get("message", ""),
                        "contesto": match.get("context", {}).get("text", ""),
                        "offset": match.get("offset", 0),
                        "lunghezza": match.get("length", 0),
                        "correzioni": match.get("replacements", [])[:3],  # Prime 3 correzioni suggerite
                        "categoria": match.get("rule", {}).get("category", {}).get("name", "Altro")
                    }
                    regole_violate.append(regola)
                
                return {
                    "errori": regole_violate,
                    "conteggio_errori": len(matches),
                    "categorie": errori_per_categoria,
                    "punteggio": max(0, min(100, 100 - len(matches) * 5)),  # Punteggio inversamente proporzionale al numero di errori
                    "servizio_disponibile": True
                }
            else:
                self.logger.error(f"Errore nella risposta LanguageTool API: {response.status_code}")
                self.servizio_disponibile = False
                return {
                    "errori": [],
                    "servizio_disponibile": False,
                    "messaggio": f"Errore API LanguageTool: {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            self.logger.error("Timeout nella richiesta a LanguageTool API")
            self.servizio_disponibile = False
            return {
                "errori": [],
                "servizio_disponibile": False,
                "messaggio": "Timeout nella richiesta a LanguageTool API"
            }
            
        except requests.exceptions.ConnectionError:
            self.logger.error("Errore di connessione a LanguageTool API")
            self.servizio_disponibile = False
            return {
                "errori": [],
                "servizio_disponibile": False,
                "messaggio": "Impossibile connettersi a LanguageTool API"
            }
            
        except Exception as e:
            self.logger.error(f"Errore durante la verifica grammaticale: {str(e)}")
            return {
                "errori": [],
                "servizio_disponibile": False,
                "messaggio": f"Errore durante l'analisi: {str(e)}"
            }
    
    def is_servizio_disponibile(self) -> bool:
        """
        Verifica se il servizio LanguageTool è attualmente disponibile.
        
        Returns:
            bool: True se il servizio è disponibile, False altrimenti.
        """
        return self.servizio_disponibile
    
    def reset_stato_servizio(self) -> None:
        """Resetta lo stato del servizio per riprovare dopo un fallimento."""
        self.servizio_disponibile = True
        self.logger.info("Stato servizio LanguageTool ripristinato")
        
    def genera_suggerimenti(self, risultati: Dict[str, Any]) -> List[str]:
        """
        Genera suggerimenti di miglioramento basati sui risultati dell'analisi grammaticale.
        
        Args:
            risultati (dict): Risultati dell'analisi grammaticale.
            
        Returns:
            list: Lista di suggerimenti per migliorare il testo.
        """
        suggerimenti = []
        
        if not risultati.get("servizio_disponibile", False):
            return ["Analisi grammaticale avanzata non disponibile."]
        
        # Estrazione degli errori più comuni per categoria
        categorie = risultati.get("categorie", {})
        if categorie:
            categoria_principale = max(categorie.items(), key=lambda x: x[1])[0]
            if categoria_principale == "Punteggiatura":
                suggerimenti.append("Rivedi la punteggiatura del testo, ci sono diversi errori.")
            elif categoria_principale == "Grammatica":
                suggerimenti.append("Presta attenzione alla grammatica, ci sono diversi errori.")
            elif categoria_principale == "Stile":
                suggerimenti.append("Considera di migliorare lo stile del testo per una maggiore chiarezza.")
        
        # Suggerimenti basati sugli errori specifici
        errori = risultati.get("errori", [])
        if len(errori) > 0:
            errori_ripetuti = {}
            for errore in errori:
                messaggio = errore.get("messaggio", "")
                if messaggio in errori_ripetuti:
                    errori_ripetuti[messaggio] += 1
                else:
                    errori_ripetuti[messaggio] = 1
            
            # Trova i 2 errori più comuni
            errori_comuni = sorted(errori_ripetuti.items(), key=lambda x: x[1], reverse=True)[:2]
            for messaggio, conteggio in errori_comuni:
                if conteggio > 1:
                    suggerimenti.append(f"Correggi gli errori ripetuti: {messaggio} ({conteggio} occorrenze)")
                else:
                    suggerimenti.append(f"Correzione consigliata: {messaggio}")
        
        # Suggerimento generale sul punteggio
        punteggio = risultati.get("punteggio", 0)
        if punteggio < 60:
            suggerimenti.append("Il testo contiene numerosi errori grammaticali che potrebbero influire sulla chiarezza.")
        elif punteggio < 80:
            suggerimenti.append("Ci sono alcuni errori grammaticali che potresti correggere per migliorare il testo.")
        
        return suggerimenti

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
        self.cache = {}
        self.logger = logging.getLogger(__name__)
        self.grammar_checker = GrammarChecker()
        
    def _get_cache_key(self, prompt):
        """
        Genera una chiave di cache basata sul prompt.
        
        Args:
            prompt (str): Il prompt da utilizzare per generare la chiave.
            
        Returns:
            str: La chiave di cache (hash MD5 del prompt).
        """
        return hashlib.md5(prompt.encode('utf-8')).hexdigest()
        
    def analizza_prompt(self, prompt):
        """
        Analizza il prompt dal punto di vista grammaticale e semantico.
        
        Args:
            prompt (str): Il prompt originale da analizzare.
        
        Returns:
            dict: Dizionario contenente l'analisi del prompt.
        """
        # Sanitizzazione dell'input
        prompt = self._sanitizza_input(prompt)
        
        if not prompt.strip():
            return {"errore": "Il prompt è vuoto."}
        
        if nlp is None:
            return {"avviso": "Analisi grammaticale non disponibile: modello spaCy non caricato."}
        
        try:
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
                "struttura": self._analizza_struttura(prompt),
                "leggibilita": self._calcola_leggibilita(prompt, doc)
            }
            
            # Analisi grammaticale avanzata con LanguageTool
            analisi_grammaticale = self.grammar_checker.verifica_testo(prompt)
            
            # Se il servizio è disponibile, incorpora i risultati
            if analisi_grammaticale.get("servizio_disponibile", False):
                analisi["grammatica"] = {
                    "punteggio": analisi_grammaticale.get("punteggio", 0),
                    "errori_conteggio": analisi_grammaticale.get("conteggio_errori", 0),
                    "categorie_errori": analisi_grammaticale.get("categorie", {}),
                    "suggerimenti": self.grammar_checker.genera_suggerimenti(analisi_grammaticale)
                }
                self.logger.info(f"Analisi grammaticale completata: {analisi_grammaticale.get('conteggio_errori', 0)} errori trovati")
            else:
                # In caso di errore, continua con un messaggio
                analisi["grammatica"] = {
                    "avviso": analisi_grammaticale.get("messaggio", "Analisi grammaticale avanzata non disponibile."),
                    "servizio_disponibile": False
                }
                self.logger.warning(f"Analisi grammaticale fallita: {analisi_grammaticale.get('messaggio', 'errore sconosciuto')}")
            
            self.ultima_analisi = analisi
            self.logger.info(f"Analisi completa: {len(prompt)} caratteri, {analisi['complessita']['livello']} complessità")
            return analisi
            
        except Exception as e:
            self.logger.error(f"Errore durante l'analisi del prompt: {str(e)}")
            return {"errore": f"Errore durante l'analisi: {str(e)}"}
    
    def _sanitizza_input(self, testo):
        """
        Sanitizza l'input utente per prevenire problemi di sicurezza.
        
        Args:
            testo (str): Il testo da sanitizzare.
            
        Returns:
            str: Il testo sanitizzato.
        """
        if not isinstance(testo, str):
            return ""
        
        # Limita la lunghezza massima
        if len(testo) > 10000:
            testo = testo[:10000]
            
        # Sanitizza HTML
        testo = html.escape(testo)
            
        return testo
    
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
        # Parole e espressioni ambigue - lista ampliata
        parole_ambigue = [
            "questo", "quello", "cosa", "fare", "forse", "potrebbe", "magari",
            "alcuni", "qualcosa", "tipo", "etc", "eccetera", "ecc", "circa",
            "praticamente", "quasi", "probabilmente"
        ]
        
        espressioni_vaghe = [
            "in qualche modo", "più o meno", "abbastanza", "una sorta di",
            "più o meno", "grossomodo", "all'incirca", "si suppone", 
            "generalmente", "tendenzialmente", "in linea di massima",
            "per così dire", "diciamo che", "si dice che"
        ]
        
        # Controllo parole ambigue
        conteggio_ambigue = sum(1 for parola in prompt.lower().split() if parola in parole_ambigue)
        
        # Controllo frasi troppo lunghe
        frasi_lunghe = len([f for f in re.split(r'[.!?]', prompt) if len(f.split()) > 25])
        
        # Controllo espressioni generiche
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
        # Sanitizzazione dell'input
        prompt = self._sanitizza_input(prompt)
        
        self.ultimo_prompt_originale = prompt
        
        # Verifica se il prompt è nella cache
        cache_key = self._get_cache_key(prompt)
        if cache_key in self.cache:
            self.logger.info("Risultato trovato in cache")
            cached_result = self.cache[cache_key]
            return cached_result
        
        if not DEEPSEEK_API_KEY:
            self.logger.error("Chiave API di DeepSeek mancante")
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
            
            # Prepara il messaggio per l'utente includendo anche l'analisi grammaticale se disponibile
            analisi_grammatica_msg = ""
            if "grammatica" in analisi and analisi["grammatica"].get("servizio_disponibile", False):
                analisi_grammatica_msg = f"""
                - Punteggio grammaticale: {analisi["grammatica"]["punteggio"]}/100
                - Errori grammaticali: {analisi["grammatica"]["errori_conteggio"]}
                """
            
            # Aggiungiamo l'analisi al contesto per il modello
            user_message = f"""
            Prompt originale:
            {prompt}
            
            Analisi del prompt:
            - Lunghezza: {analisi['lunghezza_caratteri']} caratteri, {analisi['lunghezza_parole']} parole
            - Complessità: {analisi['complessita']['livello']} ({analisi['complessita']['punteggio']}/10)
            - Chiarezza: {analisi['chiarezza']['livello']} ({analisi['chiarezza']['punteggio']}/10)
            - Leggibilità (Gulpease): {analisi.get('leggibilita', {}).get('gulpease', 'N/A')} - {analisi.get('leggibilita', {}).get('difficolta', 'N/A')}
            {analisi_grammatica_msg}
            
            Migliora questo prompt seguendo i principi indicati e rispondi in formato JSON.
            """
            
            # Chiamata API con il nuovo metodo
            response_data = self._chiama_api_deepseek(system_prompt, user_message)
            
            # Estrazione della risposta
            risultato_json = response_data["choices"][0]["message"]["content"]
            
            # Pulizia dei caratteri speciali JSON
            risultato_json = risultato_json.strip()
            if risultato_json.startswith("```json"):
                risultato_json = risultato_json[7:]
            if risultato_json.endswith("```"):
                risultato_json = risultato_json[:-3]
            
            risultato = json.loads(risultato_json)
            
            self.ultimo_prompt_migliorato = risultato["prompt_migliorato"]
            
            # Combina i suggerimenti dell'API con eventuali suggerimenti grammaticali
            suggerimenti_api = risultato["suggerimenti"]
            suggerimenti_grammaticali = []
            
            if "grammatica" in analisi and analisi["grammatica"].get("servizio_disponibile", False):
                suggerimenti_grammaticali = analisi["grammatica"].get("suggerimenti", [])
            
            # Combina i suggerimenti, evitando duplicati
            tutti_suggerimenti = suggerimenti_api.copy()
            for sugg in suggerimenti_grammaticali:
                if sugg not in tutti_suggerimenti:
                    tutti_suggerimenti.append(sugg)
            
            self.ultimi_suggerimenti = tutti_suggerimenti
            
            # Salva in cache
            risultato_tuple = (
                risultato["prompt_migliorato"],
                tutti_suggerimenti,
                risultato["spiegazione"]
            )
            self.cache[cache_key] = risultato_tuple
            
            return risultato_tuple
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Errore nel parsing JSON: {str(e)}")
            return (
                "Si è verificato un errore nel formato della risposta.",
                ["Riprova con un prompt diverso"],
                f"Errore di formato: {str(e)}"
            )
        except Exception as e:
            self.logger.error(f"Errore durante il miglioramento del prompt: {str(e)}")
            return (
                "Si è verificato un errore durante l'elaborazione.",
                ["Riprova con un prompt diverso", "Verifica la connessione internet"],
                f"Errore: {str(e)}"
            ) Estrazione della risposta
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
            
            # Salva in cache
            risultato_tuple = (
                risultato["prompt_migliorato"],
                risultato["suggerimenti"],
                risultato["spiegazione"]
            )
            self.cache[cache_key] = risultato_tuple
            
            return risultato_tuple
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Errore nel parsing JSON: {str(e)}")
            return (
                "Si è verificato un errore nel formato della risposta.",
                ["Riprova con un prompt diverso"],
                f"Errore di formato: {str(e)}"
            )
        except Exception as e:
            self.logger.error(f"Errore durante il miglioramento del prompt: {str(e)}")
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
        
        try:    
            # Analisi dei prompt
            if nlp:
                # Analizziamo entrambi i prompt
                analisi_orig = self.analizza_prompt(prompt_originale)
                analisi_migl = self.analizza_prompt(prompt_migliorato)
                
                # Confronto degli indici di leggibilità
                gulpease_orig = analisi_orig.get('leggibilita', {}).get('gulpease', 50)
                gulpease_migl = analisi_migl.get('leggibilita', {}).get('gulpease', 50)
                
                # Confronto della chiarezza
                chiarezza_orig = analisi_orig.get('chiarezza', {}).get('punteggio', 5)
                chiarezza_migl = analisi_migl.get('chiarezza', {}).get('punteggio', 5)
                
                # Confronto della struttura
                struttura_orig = analisi_orig.get('struttura', {})
                struttura_migl = analisi_migl.get('struttura', {})
                
                # Calcolo punteggi strutturali
                punti_struttura_orig = sum(1 for k, v in struttura_orig.items() if v is True)
                punti_struttura_migl = sum(1 for k, v in struttura_migl.items() if v is True)
                
                # Differenze percentuali
                diff_gulpease = ((gulpease_migl - gulpease_orig) / max(1, gulpease_orig)) * 100
                diff_chiarezza = ((chiarezza_migl - chiarezza_orig) / max(1, chiarezza_orig)) * 100
                diff_struttura = punti_struttura_migl - punti_struttura_orig
                
                # Ponderazione dei fattori
                punteggio = 60  # Base per non partire da zero
                punteggio += min(20, max(-20, diff_gulpease * 0.4))  # Max ±20 punti
                punteggio += min(15, max(-15, diff_chiarezza * 3))   # Max ±15 punti
                punteggio += min(5, max(-5, diff_struttura * 2.5))   # Max ±5 punti
                
                self.logger.info(f"Punteggio qualità calcolato: {round(punteggio)}")
                
                return max(1, min(100, round(punteggio)))
            else:
                # Metodo semplificato se spaCy non è disponibile
                diff_lunghezza = len(prompt_migliorato) / max(1, len(prompt_originale))
                punteggio_lunghezza = min(100, max(0, 50 + (diff_lunghezza - 1) * 30))
                
                # Calcolo miglioramenti strutturali basati su pattern semplici
                struttura_orig = bool(re.search(r'[\n\r][ \t]*[-*•][ \t]', prompt_originale))
                struttura_migl = bool(re.search(r'[\n\r][ \t]*[-*•][ \t]', prompt_migliorato))
                
                punteggio = punteggio_lunghezza
                if not struttura_orig and struttura_migl:
                    punteggio += 15  # Premio per aggiunta di struttura
                
                self.logger.info(f"Punteggio qualità semplificato: {round(punteggio)}")
                
                return max(1, min(100, round(punteggio)))
                
        except Exception as e:
            self.logger.error(f"Errore nel calcolo del punteggio di qualità: {str(e)}")
            # Valore predefinito in caso di errore
            return 75

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
            
        with gr.Accordion("Analisi grammaticale", open=False):
            analisi_grammaticale = gr.JSON(label="Analisi grammaticale avanzata")
            controlla_grammatica_btn = gr.Button("🔤 Controlla grammatica")
            status_grammatica = gr.Textbox(
                label="Stato servizio", 
                value="Servizio LanguageTool disponibile",
                interactive=False
            )
            reset_servizio_btn = gr.Button("🔄 Riprova connessione a LanguageTool")
            
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
            
            ## Servizi integrati
            
            Questo strumento utilizza diversi servizi per analizzare e migliorare i tuoi prompt:
            
            1. **DeepSeek AI**: Utilizzato per il miglioramento del prompt
            2. **LanguageTool**: Servizio di correzione grammaticale avanzata
            3. **SpaCy**: Libreria per l'analisi linguistica in italiano
            
            Alcuni servizi potrebbero non essere sempre disponibili. In caso di problemi con uno dei servizi, l'applicazione continuerà a funzionare utilizzando i servizi disponibili.
            """)
            
        # Funzioni per gestire gli eventi
        def migliora_prompt_click(prompt):
            if not prompt or not prompt.strip():
                return "", [], "", gr.update(value=0), {}, gr.update(value="Servizio non utilizzato")
                
            # Simuliamo un breve caricamento per dare l'impressione di elaborazione
            time.sleep(0.5)
            
            prompt_migliorato, suggerimenti_list, spiegazione_testo = assistente.migliora_prompt(prompt)
            punteggio_qualita = assistente.genera_punteggio_qualita(prompt, prompt_migliorato)
            
            # Verifica lo stato del servizio LanguageTool
            status_msg = "Servizio LanguageTool disponibile"
            if not assistente.grammar_checker.is_servizio_disponibile():
                status_msg = "Servizio LanguageTool non disponibile. Alcune funzionalità di analisi grammaticale sono disabilitate."
            
            # Formattazione dei suggerimenti per il dataframe
            suggerimenti_df = [[s] for s in suggerimenti_list]
            
            return prompt_migliorato, suggerimenti_df, spiegazione_testo, punteggio_qualita, {}, gr.update(value=status_msg)
        
        def analizza_prompt_click(prompt):
            if not prompt or not prompt.strip():
                return {}
            
            analisi = assistente.analizza_prompt(prompt)
            return analisi
            
        def controlla_grammatica_click(prompt):
            if not prompt or not prompt.strip():
                return {}, gr.update(value="Nessun testo da analizzare")
                
            analisi = assistente.analizza_prompt(prompt)
            if "grammatica" in analisi:
                status_msg = "Servizio LanguageTool disponibile"
                if not analisi["grammatica"].get("servizio_disponibile", False):
                    status_msg = analisi["grammatica"].get("avviso", "Servizio LanguageTool non disponibile")
                return analisi.get("grammatica", {}), gr.update(value=status_msg)
            return {}, gr.update(value="Analisi grammaticale non disponibile")
        
        def reset_servizio_click():
            assistente.grammar_checker.reset_stato_servizio()
            return gr.update(value="Connessione a LanguageTool ripristinata. Riprova l'analisi.")
        
        def cancel_inputs():
            return "", "", [], "", 0, {}, {}, gr.update(value="Servizio non utilizzato")
        
        # Collegamenti degli eventi
        submit_btn.click(
            migliora_prompt_click,
            inputs=[input_prompt],
            outputs=[output_prompt, suggerimenti, spiegazione, punteggio, analisi_output, status_grammatica]
        )
        
        analizza_btn.click(
            analizza_prompt_click,
            inputs=[input_prompt],
            outputs=[analisi_output]
        )
        
        controlla_grammatica_btn.click(
            controlla_grammatica_click,
            inputs=[input_prompt],
            outputs=[analisi_grammaticale, status_grammatica]
        )
        
        reset_servizio_btn.click(
            reset_servizio_click,
            inputs=[],
            outputs=[status_grammatica]
        )
        
        clear_btn.click(
            cancel_inputs,
            inputs=[],
            outputs=[input_prompt, output_prompt, suggerimenti, spiegazione, punteggio, analisi_output, analisi_grammaticale, status_grammatica]
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
