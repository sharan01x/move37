#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Transcription utilities for the Move 37 application.

This module provides utilities for extracting text content from various file formats
including text files, PDFs, Word documents, Markdown, and audio files.
"""

import os
import tempfile
import logging
import traceback
from typing import Dict, Any, Optional, Union, Tuple
from pathlib import Path

# Text extraction libraries
import PyPDF2
import docx
import markdown

# Audio transcription libraries
import speech_recognition as sr
from pydub import AudioSegment

from app.core.config import TRANSCRIPTION_SERVICE, ASSEMBLYAI_API_KEY, GOOGLE_SPEECH_API_KEY
from app.models.models import TranscriptionResult

logger = logging.getLogger(__name__)
# Set logging level to DEBUG for this module
logger.setLevel(logging.DEBUG)


class TranscriptionUtil:
    """Utility for extracting text from various file formats and transcribing audio files."""
    
    @staticmethod
    def extract_text_from_file(file_path: Union[str, Path], file_type: Optional[str] = None) -> Tuple[str, str]:
        """
        Extract text content from a file based on its type.
        
        Args:
            file_path: Path to the file
            file_type: MIME type of the file (optional, will be determined from extension if not provided)
            
        Returns:
            A tuple containing (extracted_text, status)
            Status can be "transcribed" or "transcription_error"
        """
        logger.debug(f"Starting text extraction for file: {file_path}, type: {file_type}")
        try:
            file_path = Path(file_path) if isinstance(file_path, str) else file_path
            logger.debug(f"File path converted to Path object: {file_path}")
            
            # Check if file exists
            if not file_path.exists():
                logger.error(f"File does not exist: {file_path}")
                return "", "transcription_error"
            
            logger.debug(f"File exists, size: {file_path.stat().st_size} bytes")
            
            # Determine file type from extension if not provided
            if not file_type:
                extension = file_path.suffix.lower()
                logger.debug(f"Determining file type from extension: {extension}")
                if extension == '.pdf':
                    file_type = 'application/pdf'
                elif extension == '.txt':
                    file_type = 'text/plain'
                elif extension == '.md':
                    file_type = 'text/markdown'
                elif extension == '.docx':
                    file_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                else:
                    file_type = 'text/plain'  # Default to text/plain
                logger.debug(f"Determined file type: {file_type}")
            
            # Extract text based on file type
            logger.debug(f"Selecting extraction method based on file type: {file_type}")
            if 'pdf' in file_type.lower():
                logger.debug(f"Using PDF extraction method for {file_path}")
                text = TranscriptionUtil._extract_text_from_pdf(file_path)
                logger.debug(f"PDF extraction complete, extracted {len(text)} characters")
                return text, "transcribed"
            elif 'word' in file_type.lower() or file_type.endswith('.docx'):
                logger.debug(f"Using Word document extraction method for {file_path}")
                text = TranscriptionUtil._extract_text_from_docx(file_path)
                logger.debug(f"Word extraction complete, extracted {len(text)} characters")
                return text, "transcribed"
            elif 'markdown' in file_type.lower() or file_path.suffix.lower() == '.md':
                logger.debug(f"Using Markdown extraction method for {file_path}")
                text = TranscriptionUtil._extract_text_from_markdown(file_path)
                logger.debug(f"Markdown extraction complete, extracted {len(text)} characters")
                return text, "transcribed"
            elif 'text' in file_type.lower() or file_path.suffix.lower() in ['.txt', '.text']:
                logger.debug(f"Using plain text extraction method for {file_path}")
                text = TranscriptionUtil._extract_text_from_text(file_path)
                logger.debug(f"Text extraction complete, extracted {len(text)} characters")
                return text, "transcribed"
            else:
                # For unsupported file types, return empty text with error status
                logger.warning(f"Unsupported file type for text extraction: {file_type}")
                return "", "transcription_error"
                
        except Exception as e:
            logger.error(f"Error extracting text from file {file_path}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return "", "transcription_error"
    
    @staticmethod
    def _extract_text_from_pdf(file_path: Path) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def _extract_text_from_docx(file_path: Path) -> str:
        """
        Extract text from a Word document.
        
        Args:
            file_path: Path to the Word document
            
        Returns:
            Extracted text content
        """
        try:
            doc = docx.Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs if paragraph.text])
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from Word document {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def _extract_text_from_markdown(file_path: Path) -> str:
        """
        Extract text from a Markdown file.
        
        Args:
            file_path: Path to the Markdown file
            
        Returns:
            Extracted text content
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
            # Just return the raw markdown text - we're not converting to HTML
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from Markdown file {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def _extract_text_from_text(file_path: Path) -> str:
        """
        Extract text from a plain text file.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            Extracted text content
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
            return text.strip()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            try:
                with open(file_path, 'r', encoding='latin-1') as file:
                    text = file.read()
                return text.strip()
            except Exception as e:
                logger.error(f"Error reading text file with latin-1 encoding {file_path}: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def transcribe_audio(audio_data: bytes, audio_format: str = "wav") -> TranscriptionResult:
        """
        Transcribe audio data.
        
        Args:
            audio_data: Audio data to transcribe.
            audio_format: Format of the audio data.
            
        Returns:
            TranscriptionResult object containing the transcribed text and confidence.
        """
        if TRANSCRIPTION_SERVICE == "local":
            return TranscriptionUtil._transcribe_local(audio_data, audio_format)
        elif TRANSCRIPTION_SERVICE == "assemblyai" and ASSEMBLYAI_API_KEY:
            return TranscriptionUtil._transcribe_assemblyai(audio_data, audio_format)
        elif TRANSCRIPTION_SERVICE == "google" and GOOGLE_SPEECH_API_KEY:
            return TranscriptionUtil._transcribe_google(audio_data, audio_format)
        else:
            # Default to local transcription
            return TranscriptionUtil._transcribe_local(audio_data, audio_format)
    
    @staticmethod
    def _transcribe_local(audio_data: bytes, audio_format: str = "wav") -> TranscriptionResult:
        """
        Transcribe audio data using local speech recognition.
        
        Args:
            audio_data: Audio data to transcribe.
            audio_format: Format of the audio data.
            
        Returns:
            TranscriptionResult object containing the transcribed text and confidence.
        """
        # Save the audio data to a temporary file
        with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        try:
            # Convert the audio to WAV format if it's not already
            if audio_format != "wav":
                audio = AudioSegment.from_file(temp_file_path, format=audio_format)
                temp_file_path = f"{temp_file_path}.wav"
                audio.export(temp_file_path, format="wav")
            
            # Transcribe the audio
            recognizer = sr.Recognizer()
            with sr.AudioFile(temp_file_path) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
                # Confidence is not available with recognize_google, so set a default
                confidence = 0.8
            
            return TranscriptionResult(text=text, confidence=confidence)
        except Exception as e:
            # Return an empty result with error message in metadata
            return TranscriptionResult(
                text="",
                confidence=0.0,
                metadata={"error": str(e)}
            )
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    
    @staticmethod
    def _transcribe_assemblyai(audio_data: bytes, audio_format: str = "wav") -> TranscriptionResult:
        """
        Transcribe audio data using AssemblyAI.
        
        Args:
            audio_data: Audio data to transcribe.
            audio_format: Format of the audio data.
            
        Returns:
            TranscriptionResult object containing the transcribed text and confidence.
        """
        # Note: This is a placeholder for AssemblyAI integration
        # In a production application, you would use AssemblyAI's API
        
        # For now, fallback to local transcription
        return TranscriptionUtil._transcribe_local(audio_data, audio_format)
    
    @staticmethod
    def _transcribe_google(audio_data: bytes, audio_format: str = "wav") -> TranscriptionResult:
        """
        Transcribe audio data using Google Speech API.
        
        Args:
            audio_data: Audio data to transcribe.
            audio_format: Format of the audio data.
            
        Returns:
            TranscriptionResult object containing the transcribed text and confidence.
        """
        # Note: This is a placeholder for Google Speech API integration
        # In a production application, you would use Google's Speech-to-Text API
        
        # For now, fallback to local transcription
        return TranscriptionUtil._transcribe_local(audio_data, audio_format)
