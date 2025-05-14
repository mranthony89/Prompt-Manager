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
import logging
import hashlib
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from logging.handlers import RotatingFileHandler
import html
from typing import Dict, List, Any, Optional, Union
from pydantic import Field
from pydantic_settings import BaseSettings
from cachetools import TTLCache
try:
    from spellchecker import SpellChecker
    spellchecker_disponibile = True
except ImportError:
    spellchecker_disponibile = False

# Classe di configurazione centralizzata
class Settings(BaseSettings):
    """
    Configurazione centralizzata per l'applicazione Prompt Perfezionatore.
    Utilizza Pydantic per la validazione e caricamento delle variabili d'ambiente.
    """
    # Configurazioni API
    deepseek_api_key: str = Field("", env="DEEPSEEK_API_KEY")
    deepseek_api_url: str = "https://api.deepseek.com/v1/chat/completions"
    
    # Limiti e timeout
    max_input_length: int = 10000
    api_timeout: int = 30
    max_retry_attempts: int = 3
    
    # Configurazioni cache
    cache_size: int = 100
    cache_ttl: int = 3600  # 1 ora in secondi
    
    # Parametri API
    deepseek_model: str = "deepseek-chat"
    deepseek_temperature: float = 0.7
    deepseek_max_tokens: int = 2000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Istanza delle configurazioni
settings = Settings()

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

# Caricamento del modello spaCy per l'analisi linguistica
try:
    nlp = spacy.load("it_core_news_sm")
    logger.info("Modello spaCy caricato con successo.")
except OSError:
    logger.error("Modello spaCy per l'italiano non trovato. Installalo con 'python -m spacy download it_core_news_sm'")
    nlp = None

def analisi_grammatica_spacy(testo, nlp):
    """
    Utilizza spaCy per una verifica grammaticale di base.
    
    Args:
        testo (str): Il testo da analizzare.
        nlp: Il modello spaCy caricato.
        
    Returns:
        dict: Risultati dell'analisi grammaticale.
    """
    doc = nlp(testo)
    
    # Analisi delle frasi
    frasi = list(doc.sents)
    
    # Verifiche di base
    errori = []
    
    # Controllo lunghezze frasi (frasi troppo lunghe potrebbero indicare problemi)
    for i, frase in enumerate(frasi):
        if len(frase) > 40:  # Frasi con più di 40 token potrebbero essere troppo lunghe
            errori.append({
                "tipo": "Frase lunga",
                "messaggio": f"La frase {i+1} è molto lunga ({len(frase)} parole), considera di spezzarla.",
                "offset": frase.start_char,
                "lunghezza": frase.end_char - frase.start_char
            })
    
    # Controllo ripetizioni di parole
    parole = [token.text.lower() for token in doc if not token.is_punct and not token.is_stop]
    conteggio_parole = {}
    for parola in parole:
        if len(parola) > 3:  # Ignora parole molto brevi
            if parola in conteggio_parole:
                conteggio_parole[parola] += 1
            else:
                conteggio_parole[parola] = 1
    
    # Identifica ripetizioni eccessive
    ripetizioni = [parola for parola, conteggio in conteggio_parole.items() if conteggio > 3]
    if ripetizioni:
        for parola in ripetizioni:
            errori.append({
                "tipo": "Ripetizione",
                "messaggio": f"La parola '{parola}' appare troppo spesso nel testo.",
                "suggerimento": "Usa sinonimi per rendere il testo più vario."
            })
    
    # Problemi di punteggiatura basilari
    testo_pulito = testo.strip()
    if testo_pulito and testo_pulito[-1] not in ".!?":
        errori.append({
            "tipo": "Punteggiatura",
            "messaggio": "Il testo non termina con un segno di punteggiatura.",
            "suggerimento": "Aggiungi un punto, un punto esclamativo o un punto interrogativo alla fine della frase."
        })
    
    # Calcola un punteggio di qualità grammaticale approssimativo
    punteggio = max(0, min(100, 100 - (len(errori) * 10)))
    
    # Genera suggerimenti
    suggerimenti = []
    if errori:
        for errore in errori:
            if "suggerimento" in errore:
                suggerimenti.append(errore["suggerimento"])
            else:
                suggerimenti.append(errore["messaggio"])
    
    return {
        "errori": errori,
        "conteggio_errori": len(errori),
        "punteggio": punteggio,
        "suggerimenti": suggerimenti,
        "servizio_disponibile": True
    }

def verifica_ortografia(testo, lingua="it_IT"):
    """
    Verifica l'ortografia utilizzando PySpellChecker.
    
    Args:
        testo (str): Il testo da verificare.
        lingua (str): Il codice della lingua. Default: "it_IT".
        
    Returns:
        dict: Risultati della verifica ortografica.
    """
    if not spellchecker_disponibile:
        return {
            "errori": [],
            "conteggio_errori": 0,
            "punteggio": 100,
            "suggerimenti": ["Verifica ortografica non disponibile."],
            "servizio_disponibile": False
        }
    
    try:
        # Inizializza SpellChecker con la lingua italiana
        spell = SpellChecker(language=lingua)
        
        # Tokenizza il testo in parole
        parole = testo.split()
        
        # Trova parole non corrette
        parole_errate = spell.unknown(parole)
        
        errori = []
        for parola in parole_errate:
            correzione = spell.correction(parola)
            alternative = spell.candidates(parola)
            
            # Indice della parola nel testo originale
            try:
                indice = testo.index(parola)
            except ValueError:
                indice = 0
            
            errori.append({
                "tipo": "Ortografia",
                "parola": parola,
                "messaggio": f"'{parola}' potrebbe essere scritto in modo errato.",
                "correzione": correzione,
                "alternative": list(alternative),
                "offset": indice,
                "lunghezza": len(parola)
            })
        
        # Calcola un punteggio (100 - percentuale di errori)
        if parole:
            punteggio = 100 - (len(parole_errate) / len(parole) * 100)
        else:
            punteggio = 100
        
        # Genera suggerimenti
        suggerimenti = []
        if errori:
            suggerimenti.append(f"Il testo contiene {len(errori)} errori ortografici.")
            for errore in errori[:3]:  # Limita a 3 suggerimenti
                suggerimenti.append(f"'{errore['parola']}' potrebbe essere corretto come '{errore['correzione']}'.")
        
        return {
            "errori": errori,
            "conteggio_errori": len(errori),
            "punteggio": max(0, min(100, punteggio)),
            "suggerimenti": suggerimenti,
            "servizio_disponibile": True
        }
    except ValueError as e:
        # Gestisce l'errore se il dizionario della lingua non è disponibile
        return {
            "errori": [],
            "conteggio_errori": 0,
            "punteggio": 100,
            "suggerimenti": [f"Dizionario per la lingua '{lingua}' non disponibile. Prova con 'en'."],
            "servizio_disponibile": False
        }
    except Exception as e:
        # Gestisce altri errori
        return {
            "errori": [],
            "conteggio_errori": 0,
            "punteggio": 100,
            "suggerimenti": [f"Errore durante la verifica ortografica: {str(e)}"],
            "servizio_disponibile": False
        }

class GrammarChecker:
    """
    Classe per la verifica grammaticale utilizzando strumenti locali.
    """
    
    def __init__(self):
        """Inizializza il verificatore grammaticale."""
        self.logger = logging.getLogger(__name__)
        self.ultimo_controllo = None
        self.servizio_disponibile = True
    
    def verifica_testo(self, testo: str, lingua: str = "it") -> Dict[str, Any]:
        """
        Verifica la grammatica e l'ortografia di un testo utilizzando strumenti locali.
        
        Args:
            testo (str): Il testo da verificare.
            lingua (str, optional): Il codice della lingua. Default: "it".
            
        Returns:
            dict: Risultato dell'analisi grammaticale.
        """
        try:
            # Utilizza spaCy per l'analisi grammaticale di base
            risultati_spacy = analisi_grammatica_spacy(testo, nlp)
            
            # Utilizza PySpellChecker per la verifica ortografica
            risultati_spell = verifica_ortografia(testo, lingua)
            
            # Combina i risultati
            errori_totali = risultati_spacy["errori"] + risultati_spell["errori"]
            suggerimenti_totali = risultati_spacy["suggerimenti"] + risultati_spell["suggerimenti"]
            
            # Calcola punteggio medio
            punteggio = (risultati_spacy["punteggio"] + risultati_spell["punteggio"]) / 2
            
            # Categorizza gli errori
            categorie = {}
            for errore in errori_totali:
                tipo = errore.get("tipo", "Altro")
                if tipo not in categorie:
                    categorie[tipo] = 0
                categorie[tipo] += 1
            
            return {
                "errori": errori_totali,
                "conteggio_errori": len(errori_totali),
                "categorie": categorie,
                "punteggio": punteggio,
                "suggerimenti": suggerimenti_totali[:5],  # Limita a 5 suggerimenti
                "servizio_disponibile": True
            }
                
        except Exception as e:
            self.logger.error(f"Errore durante l'analisi grammaticale locale: {str(e)}")
            return {
                "errori": [],
                "conteggio_errori": 0,
                "categorie": {},
                "punteggio": 0,
                "suggerimenti": ["Analisi grammaticale non disponibile a causa di un errore."],
                "servizio_disponibile": False,
                "messaggio": str(e)
            }
    
    def is_servizio_disponibile(self) -> bool:
        """
        Verifica se il servizio è disponibile.
        
        Returns:
            bool: True se il servizio è disponibile, False altrimenti.
        """
        return self.servizio_disponibile
    
    def reset_stato_servizio(self) -> None:
        """Resetta lo stato del servizio."""
        self.servizio_disponibile = True
        self.logger.info("Stato servizio verificatore grammaticale ripristinato")
        
    def genera_suggerimenti(self, risultati: Dict[str, Any]) -> List[str]:
        """
        Restituisce i suggerimenti già inclusi nei risultati.
        
        Args:
            risultati (dict): Risultati dell'analisi grammaticale.
            
        Returns:
            list: Lista di suggerimenti per migliorare il testo.
        """
        if not risultati.get("servizio_disponibile", False):
            return ["Analisi grammaticale avanzata non disponibile."]
        
        # Restituisci i suggerimenti già inclusi nei risultati
        return risultati.get("suggerimenti", [])
 
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
        # Utilizzo di TTLCache invece di dict standard
        self.cache = TTLCache(maxsize=settings.cache_size, ttl=settings.cache_ttl)
        self.logger = logging.getLogger(__name__)
        self.grammar_checker = GrammarChecker()
        
    def _get_cache_key(self, prompt: str) -> str:
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
            
            # Analisi grammaticale con strumenti locali
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
    
    def _sanitizza_input(self, testo: str) -> str:
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
        if len(testo) > settings.max_input_length:
            testo = testo[:settings.max_input_length]
            self.logger.warning(f"Input troncato a {settings.max_input_length} caratteri")
            
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
        
    def _calcola_leggibilita(self, testo, doc):
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
        }
        
    @retry(
        stop=stop_after_attempt(settings.max_retry_attempts), 
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException)
    )
    def _chiama_api_deepseek(self, system_prompt: str, user_message: str, 
                             model: str = None, temperatura: float = None) -> Dict[str, Any]:
        """
        Chiama l'API DeepSeek con gestione degli errori migliorata.
        
        Args:
            system_prompt (str): Il prompt di sistema.
            user_message (str): Il messaggio dell'utente.
            model (str, optional): Il modello da utilizzare. Default: settings.deepseek_model.
            temperatura (float, optional): La temperatura per la generazione. Default: settings.deepseek_temperature.
            
        Returns:
            dict: La risposta dell'API.
            
        Raises:
            requests.exceptions.RequestException: Se la richiesta all'API fallisce dopo i tentativi.
        """
        # Usa i valori predefiniti dalle impostazioni se non specificati
        model = model or settings.deepseek_model
        temperatura = temperatura or settings.deepseek_temperature
        
        url = settings.deepseek_api_url
        
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperatura,
            "max_tokens": settings.deepseek_max_tokens
        }
        
        self.logger.info(f"Invio richiesta a DeepSeek API. Model: {model}, Content length: {len(user_message)}")
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=settings.api_timeout)
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
            raise
            
    def migliora_prompt(self, prompt: str) -> tuple:
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
        
        if not settings.deepseek_api_key:
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
            )
