---
created: 2025-07-02 (Wednesday) 18:21
updated: 2025-07-14 (Monday) 17:04
---
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a legal case file management system (LawPass) that automates the organization and processing of legal documents from electronic litigation downloads. The system follows a 5-step pipeline approach to standardize legal case file management.

## Architecture

### Core Pipeline Steps
The system operates through 5 sequential steps, each handled by a dedicated script:

1. **Step 1** (`step1_copy_case_path.py`): Interactive case folder selection
2. **Step 2** (`step2_create_standard_folders.py`): Creates standardized folder structure (0_INBOX, 1_기본정보, 2_사건개요, etc.)
3. **Step 3** (`step3_casefiles_importer.py`): Imports files from electronic litigation download folder
4. **Step 4** (`step4_casefiles_renamer.py`): Renames files according to standardized naming conventions
5. **Step 5** (`step5_casefiles_extractor.py`): Extracts text from PDFs and converts to markdown format

### Key Components

- **Main Runner**: `run_lawpass_casefiles_management_system.py` - Interactive pipeline orchestrator with user confirmations
- **Configuration**: `config.yaml` - Comprehensive configuration including file naming rules, OCR settings, and templates
- **Case Path Storage**: `case_path.txt` - Stores selected case folder path between steps
- **Tools Directory**: Independent utilities for specific tasks (audio processing, folder packaging, etc.)

### Configuration System

The `config.yaml` file contains extensive configuration sections:
- **General settings**: Source/backup folder paths
- **File naming rules**: Prefix patterns for different document types (증거, 서면, 판결)
- **Text extraction**: OCR settings, Google Cloud Vision API, templates for evidence/submissions/judgments
- **Backup policies**: Retention and cleanup settings
- **Logging**: Comprehensive logging configuration

## Common Development Tasks

### Running the System
```bash
# Run the complete pipeline interactively
python run_lawpass_casefiles_management_system.py

# Run only Step 4 (file renaming)
python run_lawpass_casefiles_management_system_step4.py

# Run individual steps
python steps/step1_copy_case_path.py
python steps/step2_create_standard_folders.py "path/to/case/folder"
python steps/step3_casefiles_importer.py "path/to/case/folder"
python steps/step4_casefiles_renamer.py "path/to/case/folder"
python steps/step5_casefiles_extractor.py --case-folder "path/to/case/folder" --evidence
```

### Dependencies
Install required packages:
```bash
pip install -r requirements.txt
```

Key dependencies include:
- Google Cloud Vision API (`google-cloud-vision`)
- PDF processing (`pdf2image`, `pillow`)
- Configuration management (`PyYAML`)
- Rich UI (`rich`)

### Environment Setup
- Requires Google Cloud Vision API credentials at path specified in `config.yaml`
- Requires Poppler binaries for PDF to image conversion
- Default paths are configured for Windows environments

## File Structure Conventions

### Standardized Folder Structure
```
Case Folder/
├── 0_INBOX/
├── 1_기본정보/
├── 2_사건개요/
├── 3_사실관계/
├── 4_기준판례/
├── 5_관련법리/
├── 6_논리구성/
├── 7_제출증거/
├── 8_제출서면/
├── 9_판결/
├── 원본폴더/        # Original files backup
└── 마크다운/        # Extracted markdown files
```

### File Naming Conventions
Files are automatically renamed with prefixes based on content type:
- `1_기본정보_`: Basic case information
- `7_제출증거_`: Evidence files (갑1, 을1, etc.)
- `8_제출서면_`: Legal submissions (소장, 답변서, 준비서면, etc.)
- `9_판결_`: Court decisions and judgments

## Text Extraction System

### Extraction Templates
The system uses structured templates for different document types:
- **Evidence Template**: Includes metadata fields like 증거명, 제출자, 증거능력여부
- **Submission Template**: Includes 서면명, 제출자, 서면요지
- **Judgment Template**: Includes 사건번호, 선고일자, 법원명

### OCR Configuration
- Primary: Google Cloud Vision API
- Fallback: Tesseract OCR (configurable)
- Supports Korean and English text recognition
- Configurable DPI settings for accuracy

## Logging and Monitoring

Logs are stored in the `logs/` directory:
- `file_manager.log`: General file operations
- `general_extractor.log`: Text extraction operations

Log rotation and retention are configurable via `config.yaml`.

## Error Handling

Each step includes comprehensive error handling and result verification:
- Pipeline stops on step failure unless explicitly skipped
- Each step validates its output before proceeding
- User confirmation required between steps
- Rollback capabilities through backup system

## Important Notes

- All Korean text should be preserved exactly as written in the codebase
- The system is designed for Windows paths but runs on WSL2 environment
- Interactive prompts are integral to the workflow - preserve user confirmation patterns
- Configuration changes should be made through `config.yaml` rather than hardcoded values
- The system maintains file integrity through comprehensive backup mechanisms