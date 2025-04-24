# Changelog

## [1.2.0] - 2025-03-08

### Removed
- **Quality Assurance Agent**: Removed the standalone Quality Assurance agent

### Changed
- **Response Evaluation**: Moved the response evaluation functionality from the Quality Assurance agent to the Conductor agent
- **Evaluation Threshold**: Changed the threshold for direct responses from 100 to 90 to allow for more immediate responses
- **Code Organization**: Streamlined the codebase by consolidating evaluation logic in the Conductor agent

## [1.1.0] - 2025-03-04

### Added
- **First Responder Agent**: New agent that quickly handles simple factual questions by directly querying an LLM
- **Quality Assurance Agent**: New agent that evaluates responses against original queries and assigns a score
- **Streaming Responses**: Added support for streaming responses to provide real-time feedback during lengthy operations
- **Enhanced API Endpoints**: Modified `/recall` and `/recall-form` endpoints to support streaming responses
- **Unit Tests**: Added tests for the new agent functionality and workflow

### Changed
- **Query Processing Workflow**: Implemented an optimized workflow to handle simple queries directly:
  - First step uses the First Responder Agent to attempt a direct answer
  - Second step uses Quality Assurance Agent to evaluate the response
  - Perfect scores (100) are returned immediately
  - Imperfect scores trigger a notification to the user and continue with the full processing pipeline
- **Response Time Improvement**: Simple factual questions now receive immediate responses
- **User Experience**: Added intermediate feedback when full query processing is required

### Technical Details
- Added `/app/agents/first_responder_agent.py`
- Added `/app/agents/quality_assurance_agent.py`
- Added `/app/utils/streaming.py` for handling streaming responses
- Modified `/app/agents/conductor_agent.py` to implement new workflow
- Modified `/app/api/main.py` to support streaming responses
- Added unit tests to validate the new functionality
