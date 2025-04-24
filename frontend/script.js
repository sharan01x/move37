document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const recordButton = document.getElementById('recordButton');
    const stopRecordingButton = document.getElementById('stopRecordingButton');
    const recordingIndicator = document.getElementById('recordingIndicator');
    const recordingTime = document.getElementById('recordingTime');
    const fileInput = document.getElementById('fileInput');
    const attachButton = document.getElementById('attachButton');
    const filePreview = document.getElementById('filePreview');
    const fileName = document.getElementById('fileName');
    const removeFileButton = document.getElementById('removeFileButton');
    const userProfileButton = document.getElementById('userProfileButton');
    const userProfilePanel = document.getElementById('userProfilePanel');
    const closeProfilePanel = document.getElementById('closeProfilePanel');
    const userFactsList = document.getElementById('userFactsList');
    const filterButtons = document.querySelectorAll('.filter-btn');
    const conversationItems = document.querySelectorAll('.conversation-item');
    const currentChatIcon = document.querySelector('.current-chat-icon');
    const currentChatName = document.querySelector('.current-chat-name');
    const tabs = document.querySelectorAll('.tab');
    const recallTabContent = document.getElementById('recallTabContent');
    const recordTabContent = document.getElementById('recordTabContent');
    const currentModeIndicator = document.getElementById('currentModeIndicator');
    const userIdDisplay = document.getElementById('userIdDisplay');
    
    // File Management Variables
    const fileManagementInterface = document.getElementById('fileManagementInterface');
    const fileUploadInput = document.getElementById('fileUploadInput');
    const fileUploadButton = document.getElementById('fileUploadButton');
    const fileList = document.getElementById('fileList');
    const refreshFileList = document.getElementById('refreshFileList');
    const deleteSelectedFiles = document.getElementById('deleteSelectedFiles');
    
    // Text content modal elements
    const textContentModal = document.createElement('div');
    textContentModal.className = 'modal';
    textContentModal.id = 'textContentModal';
    textContentModal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>File Content</h2>
                <span class="close-modal">&times;</span>
            </div>
            <div class="modal-body">
                <textarea id="textContentArea" rows="15"></textarea>
            </div>
            <div class="modal-footer">
                <button id="saveTextContent" class="modal-button save" disabled>Save</button>
                <button id="cancelTextContent" class="modal-button cancel">Cancel</button>
            </div>
        </div>
    `;
    document.body.appendChild(textContentModal);
    
    // API endpoint
    const apiBaseUrl = 'http://localhost:8000';
    const wsBaseUrl = 'ws://localhost:8000';  // Add WebSocket base URL

    // User ID state
    let userId = 'user123';
    
    // Selected file for upload
    let selectedFile = null;
    
    // Recording variables
    let mediaRecorder = null;
    let audioChunks = [];
    let recordingInterval = null;
    let recordingSeconds = 0;
    
    // User facts state
    let userFacts = [];
    let currentCategory = 'all';
    
    // Current agent and record type
    let currentAgentId = "all";  // Changed from currentAgent to currentAgentId
    let currentRecordType = 'submissions';
    
    // Current mode (recall or record)
    let currentMode = 'recall';
    
    // Conversation history for each agent
    const conversationHistory = {
        'all': [],           // Using agentId consistently
        'first_responder': [],
        'number_ninja': [],
        'persephone': [],
        'librarian': [],
        'butterfly': []
    };
    
    // Record history for each type
    const recordHistory = {
        'submissions': [],
        'files': [],
        'voice': [],
        'video': [],
        'photos': []
    };
    
    // Selected files for deletion
    let selectedFiles = new Set();
    
    // WebSocket connections
    let recallWsConnection = null;  // For READ operations (recall queries, user facts retrieval, file listings)
    let recordWsConnection = null;  // For WRITE operations (submissions, file modifications, user facts changes)
    let recallWsReconnectAttempts = 0;
    let recordWsReconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 5;

    // Conversation management
    let currentConversationId = null;
    
    // Agent name mappings and helper functions
    const agentNameMappings = {
        internalToDisplay: {
            'all': 'Group Chat',
            'first_responder': 'First Responder',
            'number_ninja': 'Number Ninja',
            'persephone': 'Persephone',
            'librarian': 'Librarian',
            'butterfly': 'Butterfly',
            'system': 'System'
        }
    };

    // Helper functions for agent name conversions
    function getDisplayName(agentId) {
        return agentNameMappings.internalToDisplay[agentId] || agentId;
    }

    // Initialize the chat interface
    init();
    
    function init() {
        console.log('Initializing chat interface');

        // Log the tabs to make sure they're being selected correctly
        console.log('Tabs:', tabs);
        tabs.forEach(tab => {
            console.log(`Tab: ${tab.dataset.tab}`);
        });
        
        // Add event listeners
        userInput.addEventListener('keydown', handleInputKeydown);
        sendButton.addEventListener('click', handleSendMessage);
        recordButton.addEventListener('click', startRecording);
        stopRecordingButton.addEventListener('click', stopRecording);
        attachButton.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', handleFileSelection);
        removeFileButton.addEventListener('click', removeSelectedFile);
        
        // User profile event listeners
        userProfileButton.addEventListener('click', toggleUserProfilePanel);
        closeProfilePanel.addEventListener('click', closeUserProfilePanelHandler);
        
        // User ID event listeners
        userIdDisplay.addEventListener('click', makeUserIdEditable);
        
        // Filter buttons event listeners
        filterButtons.forEach(button => {
            button.addEventListener('click', () => {
                filterUserFacts(button.dataset.category);
            });
        });
        
        // Tab switching event listeners
        tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                console.log(`Tab clicked: ${tab.dataset.tab}`);
                console.log(`Tab element:`, tab);
                switchTab(tab.dataset.tab);
            });
        });
        
        // Conversation item event listeners
        document.querySelectorAll('#recallTabContent .conversation-item').forEach(item => {
            item.addEventListener('click', () => {
                const agentId = item.dataset.agent;  // This should already be the internal name
                console.log('Switching to agent:', agentId);
                switchConversation(agentId);
            });
        });
        
        // Record type event listeners
        document.querySelectorAll('#recordTabContent .conversation-item').forEach(item => {
            item.addEventListener('click', () => {
                const recordType = item.dataset.recordType;
                console.log('Switching to record type:', recordType);
                switchRecordType(recordType);
            });
        });
        
        // Set initial record type
        currentRecordType = document.querySelector('#recordTabContent .conversation-item.active').dataset.recordType;
        
        // Initialize file management
        initFileManagement();
        
        // Connect WebSockets for READ and WRITE operations
        connectRecallWebSocket(); // For READ operations
        connectRecordWebSocket(); // For WRITE operations
    }
    
    // User ID editing functions
    function makeUserIdEditable() {
        const currentUserId = userIdDisplay.textContent;
        userIdDisplay.contentEditable = true;
        userIdDisplay.classList.add('editing');
        userIdDisplay.focus();

        // Save on enter or blur
        const saveUserId = () => {
            const newUserId = userIdDisplay.textContent.trim();
            if (newUserId && newUserId !== currentUserId) {
                userId = newUserId;
            } else {
                userIdDisplay.textContent = currentUserId;
            }
            userIdDisplay.contentEditable = false;
            userIdDisplay.classList.remove('editing');
        };

        userIdDisplay.addEventListener('blur', saveUserId, { once: true });
        userIdDisplay.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                userIdDisplay.blur();
            }
            if (e.key === 'Escape') {
                userIdDisplay.textContent = currentUserId;
                userIdDisplay.blur();
            }
        });
    }
    
    // Tab Switching Functions
    function switchTab(tabName) {
        console.log(`Switching to tab: ${tabName}`);
        
        // Update active tab
        tabs.forEach(tab => {
            if (tab.dataset.tab === tabName) {
                tab.classList.add('active');
                console.log(`Set tab ${tabName} to active`);
            } else {
                tab.classList.remove('active');
            }
        });
        
        // Update current mode
        currentMode = tabName;
        console.log(`Current mode updated to: ${currentMode}`);
        
        // Update mode indicator
        if (tabName === 'recall') {
            currentModeIndicator.textContent = 'Recall Mode';
            currentModeIndicator.className = 'recall-mode';
        } else {
            currentModeIndicator.textContent = 'Record Mode';
            currentModeIndicator.className = 'record-mode';
        }
        
        // Get reference to main content and interfaces
        const mainContent = document.querySelector('.main-content');
        const fileManagementInterface = document.querySelector('.file-management-interface');
        const chatMessages = document.querySelector('.chat-messages');
        const chatInput = document.querySelector('.chat-input-container');
        
        // Show/hide tab content
        if (tabName === 'recall') {
            console.log('Showing recall tab content, hiding record tab content');
            recallTabContent.style.display = 'block';
            recordTabContent.style.display = 'none';
            
            // Reset file management interface
            fileManagementInterface.style.display = 'none';
            mainContent.classList.remove('files-active');
            chatMessages.style.display = 'flex';
            chatInput.style.display = 'flex';
            
            // Update chat header for recall mode
            updateChatHeaderForRecall();
            
            // Display conversation history for current agent
            displayConversationHistory(currentAgentId);
            
            // Update placeholder text for recall
            userInput.placeholder = "Ask a question to recall information...";
        } else {
            console.log('Showing record tab content, hiding recall tab content');
            recallTabContent.style.display = 'none';
            recordTabContent.style.display = 'block';
            
            // Reset file management interface based on current record type
            if (currentRecordType === 'files') {
                fileManagementInterface.style.display = 'flex';
                chatMessages.style.display = 'none';
                chatInput.style.display = 'none';
                mainContent.classList.add('files-active');
                loadFileList(); // Reload file list when switching back to files
            } else {
                fileManagementInterface.style.display = 'none';
                chatMessages.style.display = 'flex';
                chatInput.style.display = 'flex';
                mainContent.classList.remove('files-active');
            }
            
            // Update chat header for record mode
            updateChatHeaderForRecord();
            
            // Display record history for current type
            displayRecordHistory(currentRecordType);
            
            // Update placeholder text for record
            userInput.placeholder = "Type your information to record...";
        }
    }
    
    // Conversation Switching Functions
    function switchConversation(agent) {
        console.log('Switching conversation to:', agent);
        
        // Update active conversation item using internal names
        document.querySelectorAll('#recallTabContent .conversation-item').forEach(item => {
            const itemAgent = item.dataset.agent;
            if (itemAgent === agent) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        
        // Update current agent
        currentAgentId = agent;
        console.log('Current agent updated to:', currentAgentId);
        
        // Update chat header
        updateChatHeaderForRecall();
        
        // Load conversation history for this agent
        displayConversationHistory(agent);

        // Focus on the chat input
        userInput.focus();
    }
    
    function updateChatHeaderForRecall() {
        // Use display name for the header text
        const displayName = getDisplayName(currentAgentId);
        currentChatName.textContent = displayName;
        
        currentChatIcon.className = 'current-chat-icon';
        
        // Define agent icon mappings
        const agentIcons = {
            'number_ninja': 'calculator',
            'first_responder': 'comment-medical', 
            'persephone': 'user-circle',
            'librarian': 'file-alt',
            'butterfly': 'broadcast-tower', 
            'all': 'users'
        };

        // Add class and icon for current agent
        const iconName = agentIcons[currentAgentId] || agentIcons.all;
        currentChatIcon.classList.add(currentAgentId || 'all');
        currentChatIcon.innerHTML = `<i class="fas fa-${iconName}"></i>`;
    }
    
    function displayConversationHistory(agent) {
        // Clear existing messages
        chatMessages.innerHTML = '';
        
        if (conversationHistory[agent]) {
            // Display messages from the specified history
            conversationHistory[agent].forEach(message => {
                // Get the score from the original message's score dot
                const originalScoreDot = message.querySelector('.score-dot');
                let score = null;
                
                if (originalScoreDot) {
                    if (originalScoreDot.classList.contains('score-100')) {
                        score = 100;
                    } else if (originalScoreDot.classList.contains('score-0')) {
                        score = 0;
                    } else if (originalScoreDot.classList.contains('score-other')) {
                        score = 50;
                    }
                    // If none of the score classes are present, score remains null
                }
                
                // Create a new message element with the same content and properties
                const newMessage = addMessageToChat(
                    message.classList.contains('user') ? 'user' : 'agent',
                    message.querySelector('.content').textContent,
                    message.querySelector('.agent-name')?.getAttribute('data-agent'),
                    score,
                    message.getAttribute('data-query-id')
                );
                
                // Copy the opacity if it exists
                if (message.style.opacity) {
                    newMessage.style.opacity = message.style.opacity;
                }
            });
        }
        
        // Scroll to bottom
        scrollToBottom();
    }
    
    // Record Type Switching Functions
    function switchRecordType(recordType) {
        // Update active record type item
        document.querySelectorAll('#recordTabContent .conversation-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`#recordTabContent .conversation-item[data-record-type="${recordType}"]`).classList.add('active');

        // Get references to the interfaces
        const fileManagementInterface = document.querySelector('.file-management-interface');
        const chatMessages = document.querySelector('.chat-messages');
        const chatInput = document.querySelector('.chat-input-container');
        const mainContent = document.querySelector('.main-content');

        // Show/hide appropriate interface based on record type
        if (recordType === 'files') {
            fileManagementInterface.style.display = 'flex';
            chatMessages.style.display = 'none';
            chatInput.style.display = 'none';
            mainContent.classList.add('files-active');
            loadFileList(); // Load the file list when switching to files view
        } else {
            fileManagementInterface.style.display = 'none';
            chatMessages.style.display = 'flex';
            chatInput.style.display = 'flex';
            mainContent.classList.remove('files-active');
        }

        // Update current record type
        currentRecordType = recordType;

        // Update UI based on record type
        updateUIForRecordType(recordType);

        // Update chat header and current chat name
        updateChatHeaderForRecord();

        // If we're switching away from files, ensure we switch to the appropriate mode
        if (recordType !== 'files') {
            if (currentMode === 'recall') {
                // Hide file management interface and show recall interface
                fileManagementInterface.style.display = 'none';
                recallTabContent.style.display = 'block';
                recordTabContent.style.display = 'none';
                chatMessages.style.display = 'flex';
                chatInput.style.display = 'flex';
                mainContent.classList.remove('files-active');
                // Update chat header for recall mode
                updateChatHeaderForRecall();
                // Display conversation history for current agent
                displayConversationHistory(currentAgentId);
            } else {
                // Show record interface for non-file types
                fileManagementInterface.style.display = 'none';
                chatMessages.style.display = 'flex';
                chatInput.style.display = 'flex';
                mainContent.classList.remove('files-active');
                // Display record history for current type
                displayRecordHistory(recordType);
            }
        }
    }
    
    function updateChatHeaderForRecord() {
        currentChatName.textContent = capitalizeFirstLetter(currentRecordType);
        currentChatIcon.className = 'current-chat-icon';
        currentChatIcon.classList.add(`record-${currentRecordType}`);
        
        // Set icon based on record type
        let iconClass = 'fa-edit';
        if (currentRecordType === 'files') iconClass = 'fa-file-alt';
        if (currentRecordType === 'voice') iconClass = 'fa-microphone';
        if (currentRecordType === 'video') iconClass = 'fa-video';
        if (currentRecordType === 'photos') iconClass = 'fa-camera';
        
        currentChatIcon.innerHTML = `<i class="fas ${iconClass}"></i>`;
    }
    
    function displayRecordHistory(recordType) {
        // Clear chat messages
        chatMessages.innerHTML = '';
        
        // Add record history
        recordHistory[recordType].forEach(message => {
            chatMessages.appendChild(message.cloneNode(true));
        });
        
        // Scroll to bottom
        scrollToBottom();
    }
    
    function updateUIForRecordType(recordType) {
        // Show/hide buttons based on record type
        if (recordType === 'voice' || recordType === 'video') {
            recordButton.style.display = 'flex';
        } else {
            recordButton.style.display = 'flex'; // Keep it visible for all types for now
        }
        
        if (recordType === 'files' || recordType === 'photos') {
            attachButton.style.display = 'flex';
        } else {
            attachButton.style.display = 'flex'; // Keep it visible for all types for now
        }
        
        // Update placeholder text based on record type
        switch (recordType) {
            case 'submissions':
                userInput.placeholder = "Type your information to record...";
                break;
            case 'files':
                userInput.placeholder = "Add a description for your file...";
                break;
            case 'voice':
                userInput.placeholder = "Add a description for your voice recording...";
                break;
            case 'video':
                userInput.placeholder = "Add a description for your video...";
                break;
            case 'photos':
                userInput.placeholder = "Add a description for your photo...";
                break;
        }
    }
    
    function getRecordTypeDescription(recordType) {
        switch (recordType) {
            case 'submissions':
                return 'Type any information you want to record.';
            case 'files':
                return 'Upload documents you want to save.';
            case 'voice':
                return 'Record audio notes for later recall.';
            case 'video':
                return 'Record video notes for later recall.';
            case 'photos':
                return 'Upload images you want to save.';
            default:
                return '';
        }
    }
    
    // User Profile Panel Functions
    function toggleUserProfilePanel() {
        userProfilePanel.classList.toggle('active');
        
        // Load user facts when the panel is opened
        if (userProfilePanel.classList.contains('active')) {
            loadUserFacts();
        }
    }
    
    function closeUserProfilePanelHandler() {
        userProfilePanel.classList.remove('active');
    }
    
    function loadUserFacts() {
        try {
            userFactsList.innerHTML = '<div class="loading-facts">Loading your information...</div>';
            
            // Ensure recall WebSocket is connected
            if (!recallWsConnection || recallWsConnection.readyState !== WebSocket.OPEN) {
                connectRecallWebSocket();
                setTimeout(loadUserFacts, 1000); // Try again after connection is established
                return;
            }
            
            // Create a unique ID for this request
            const requestId = generateQueryId();
            
            // Send the request through WebSocket
            recallWsConnection.send(JSON.stringify({
                type: "user_facts_get",  // Using lowercase to match backend enum
                request_id: requestId,
                data: {
                    user_id: userId
                }
            }));
            
            console.log('Sent user facts request via WebSocket with type: user_facts_get');
        } catch (error) {
            console.error('Error loading user facts via WebSocket:', error);
            userFactsList.innerHTML = '<div class="loading-facts">Failed to load information. Please try again.</div>';
        }
    }
    
    function displayUserFacts(facts) {
        if (facts.length === 0) {
            userFactsList.innerHTML = '<div class="loading-facts">No information available yet.</div>';
            return;
        }
        
        // Filter facts by category if needed
        const filteredFacts = currentCategory === 'all' 
            ? facts 
            : facts.filter(fact => fact.category === currentCategory);
        
        if (filteredFacts.length === 0) {
            userFactsList.innerHTML = `<div class="loading-facts">No information in the "${currentCategory}" category.</div>`;
            return;
        }
        
        // Sort facts by recording date (newest first)
        filteredFacts.sort((a, b) => new Date(b.recorded_at) - new Date(a.recorded_at));
        
        // Create HTML for facts
        const factsHTML = filteredFacts.map(fact => {
            const recordedDate = new Date(fact.recorded_at || fact.created_at);
            const formattedDate = formatDateTimeForDisplay(recordedDate);
            
            return `
                <div class="fact-item" data-id="${fact.id}">
                    <div class="fact-content">${fact.fact}</div>
                    <div class="fact-metadata">
                        <span class="fact-category">${fact.category.replace('_', ' ')}</span>
                        <span class="fact-date">Recorded: ${formattedDate}</span>
                    </div>
                    <div class="fact-actions">
                        <button class="fact-action-btn delete-btn">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        
        userFactsList.innerHTML = factsHTML;
        
        // Add event listeners to delete buttons
        document.querySelectorAll('.delete-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const factId = button.closest('.fact-item').dataset.id;
                deleteFact(factId);
            });
        });
    }
    
    function filterUserFacts(category) {
        currentCategory = category;
        
        // Update active filter button
        filterButtons.forEach(button => {
            if (button.dataset.category === category) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
        
        // Display filtered facts
        displayUserFacts(userFacts);
    }
    
    function deleteFact(factId) {
        const confirmed = confirm('Are you sure you want to delete this fact?');
        if (!confirmed) return;
        
        try {
            // Ensure record WebSocket is connected
            if (!recordWsConnection || recordWsConnection.readyState !== WebSocket.OPEN) {
                connectRecordWebSocket();
                setTimeout(() => deleteFact(factId), 1000); // Try again after connection is established
                return;
            }
            
            // Create a unique ID for this request
            const requestId = generateQueryId();
            
            // Send the delete request through WebSocket
            recordWsConnection.send(JSON.stringify({
                type: "user_facts_delete",  // Using lowercase to match backend enum
                request_id: requestId,
                data: {
                    user_id: userId,
                    fact_id: factId
                }
            }));
            
            console.log('Sent fact deletion request via WebSocket with type: user_facts_delete');
            
            // We'll show a temporary visual feedback, but the actual removal will happen when we receive
            // the response from the WebSocket in the handleWebSocketMessage function
        } catch (error) {
            console.error('Error deleting fact via WebSocket:', error);
            alert('Failed to delete fact. Please try again.');
        }
    }
    
    // Chat Interface Functions
    function handleInputKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    }
    
    // Add a new function to update the loading indicator with interim messages
    function updateLoadingIndicator(operationId, message) {
        let loadingMessage = document.querySelector('.message.loading');
        if (!loadingMessage) {
            loadingMessage = document.createElement('div');
            loadingMessage.className = 'message loading';
            
            const messageContent = document.createElement('div');
            messageContent.className = 'message-content';
            
            const loadingDots = document.createElement('div');
            loadingDots.className = 'loading-dots';
            loadingDots.innerHTML = '<span></span><span></span><span></span>';
            
            messageContent.appendChild(loadingDots);
            loadingMessage.appendChild(messageContent);
            chatMessages.appendChild(loadingMessage);
        }
        
        const messageContent = loadingMessage.querySelector('.message-content');
        messageContent.textContent = message;
        
        // Add loading dots back
        const loadingDots = document.createElement('div');
        loadingDots.className = 'loading-dots';
        loadingDots.innerHTML = '<span></span><span></span><span></span>';
        messageContent.appendChild(loadingDots);
        
        // Set a timeout to remove the loading indicator if no response is received
        setTimeout(() => {
            if (document.querySelector('.message.loading')) {
                removeLoadingIndicator();
            }
        }, 10000);  // 10 seconds timeout
        
        scrollToBottom();
    }
    
    function removeLoadingIndicator() {
        const loadingDiv = document.querySelector('.message.loading');
        if (loadingDiv) {
            loadingDiv.remove();
        }
    }
    
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Recording Functions
    async function startRecording() {
        try {
            // Determine media type based on record type
            const mediaConstraints = { audio: true };
            if (currentRecordType === 'video') {
                mediaConstraints.video = true;
            }
            
            const stream = await navigator.mediaDevices.getUserMedia(mediaConstraints);
            
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = () => {
                const mimeType = currentRecordType === 'video' ? 'video/webm' : 'audio/wav';
                const fileName = currentRecordType === 'video' ? 'recording.webm' : 'recording.wav';
                
                const mediaBlob = new Blob(audioChunks, { type: mimeType });
                selectedFile = new File([mediaBlob], fileName, { type: mimeType });
                
                // Show file preview
                fileName.textContent = currentRecordType === 'video' ? 'Video recording' : 'Voice recording';
                filePreview.style.display = 'flex';
                
                // Hide recording indicator
                recordingIndicator.style.display = 'none';
                
                // Clear recording timer
                clearInterval(recordingInterval);
                recordingSeconds = 0;
                
                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
            };
            
            // Start recording
            mediaRecorder.start();
            
            // Show recording indicator
            recordingIndicator.style.display = 'flex';
            recordingTime.textContent = '0:00';
            
            // Start recording timer
            recordingInterval = setInterval(updateRecordingTime, 1000);
            
        } catch (error) {
            console.error('Error starting recording:', error);
            alert('Could not access microphone/camera. Please check your permissions.');
        }
    }
    
    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
    }
    
    function updateRecordingTime() {
        recordingSeconds++;
        const minutes = Math.floor(recordingSeconds / 60);
        const seconds = recordingSeconds % 60;
        recordingTime.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
    
    // File Handling Functions
    function handleFileSelection(e) {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            
            // If we're in the Butterfly agent, validate that only images and videos are allowed
            if (currentAgentId === 'butterfly') {
                const fileType = file.type;
                // Only allow image and video types
                if (!fileType.startsWith('image/') && !fileType.startsWith('video/')) {
                    addMessageToChat('agent', "Only images and videos are supported for social media posts.", 'system');
                    fileInput.value = '';
                    return;
                }
            }
            
            selectedFile = file;
            
            // Show file preview
            fileName.textContent = selectedFile.name;
            filePreview.style.display = 'flex';
        }
    }
    
    function removeSelectedFile() {
        selectedFile = null;
        fileInput.value = '';
        filePreview.style.display = 'none';
    }
    
    // Helper Functions
    function capitalizeFirstLetter(string) {
        return string.charAt(0).toUpperCase() + string.slice(1);
    }
    
    // Add message to chat interface
    function addMessageToChat(type, content, agentId = null, score = null, queryId = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        // Add query ID if provided
        if (queryId) {
            messageDiv.setAttribute('data-query-id', queryId);
        }
        
        if (type === 'status') {
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            
            // Create loading dots first
            const loadingDots = document.createElement('div');
            loadingDots.className = 'loading-dots';
            loadingDots.innerHTML = '<span></span><span></span><span></span>';
            contentDiv.appendChild(loadingDots);
            
            // Add text after dots
            const textSpan = document.createElement('span');
            textSpan.textContent = content;
            contentDiv.appendChild(textSpan);
            
            messageDiv.appendChild(contentDiv);
        } else {
            // Set opacity based on score
            if (score !== null) {
                messageDiv.style.opacity = Math.max(0.4, score / 100);
            }
            
            if (agentId) {
                const agentNameDiv = document.createElement('div');
                agentNameDiv.className = 'agent-name';
                // Set the data-agent attribute for the agent ID
                agentNameDiv.setAttribute('data-agent', agentId);
                // Add the agent's color class
                agentNameDiv.classList.add(`agent-${agentId}`);
                // Use display name for the text content
                agentNameDiv.textContent = getDisplayName(agentId);
                
                const scoreDot = document.createElement('span');
                scoreDot.className = 'score-dot';
                
                // For agent messages, only add blinking if no score is provided
                if (type === 'agent' && score === null) {
                    scoreDot.classList.add('blinking');
                } else if (score !== null) {
                    // If score is provided, set the appropriate class
                    if (score === 100) {
                        scoreDot.classList.add('score-100');
                    } else if (score === 0) {
                        scoreDot.classList.add('score-0');
                    } else {
                        scoreDot.classList.add('score-other');
                    }
                }
                agentNameDiv.appendChild(scoreDot);
                messageDiv.appendChild(agentNameDiv);
            }
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'content';
            contentDiv.textContent = content;
            messageDiv.appendChild(contentDiv);
        }
        
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        
        return messageDiv;
    }
    
    // Handle status updates
    function handleStatusUpdate(message) {
        if (message.data && message.data.message) {
            // If this is a final status update (DONE), remove all status messages
            if (message.data.is_final) {
                const existingStatus = document.querySelectorAll('.message.status');
                existingStatus.forEach(msg => msg.remove());
                return;
            }
            
            // Update the status message
            const existingStatus = document.querySelectorAll('.message.status');
            existingStatus.forEach(msg => msg.remove());
            addMessageToChat('status', message.data.message);
        }
    }
    
    // WebSocket connection management for READ operations (recall queries, user facts retrieval, file listing)
    function connectRecallWebSocket() {
        if (recallWsConnection) {
            return;
        }
        
        const wsUrl = `${wsBaseUrl}/ws/recall`;
        console.log('Connecting to Recall WebSocket (READ operations):', wsUrl);
        
        recallWsConnection = new WebSocket(wsUrl);
        
        recallWsConnection.onopen = () => {
            console.log('Recall WebSocket connection established');
            recallWsReconnectAttempts = 0;
        };
        
        recallWsConnection.onclose = () => {
            console.log('Recall WebSocket connection closed');
            addMessageToChat('status', 'Connection lost. Please refresh the page to reconnect.');
            
            // Attempt to reconnect if under max attempts
            if (recallWsReconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                recallWsReconnectAttempts++;
                setTimeout(connectRecallWebSocket, 3000 * recallWsReconnectAttempts);
            }
        };
        
        recallWsConnection.onerror = (error) => {
            console.error('Recall WebSocket error:', error);
            addMessageToChat('status', 'Connection error occurred. Attempting to reconnect...');
        };
        
        recallWsConnection.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                console.log('Received Recall WebSocket message:', message);
                
                if (!message || !message.type) {
                    console.warn('Invalid recall message format:', message);
                    return;
                }
                
                switch (message.type) {
                    case 'status_update':
                        handleStatusUpdate(message);
                        break;
                    case 'agent_response':
                        if (message.data) {
                            console.log('Handling agent response:', message.data);
                            handleAgentResponse(message.data);
                        }
                        break;
                    case 'agent_responses':
                        if (message.data && Array.isArray(message.data)) {
                            message.data.forEach(response => {
                                console.log('Handling agent response from array:', response);
                                handleAgentResponse(response);
                            });
                        }
                        break;
                    case 'quality_updates':
                        if (message.data) {
                            console.log('Handling quality updates:', message.data);
                            handleQualityUpdates(message.data);
                        }
                        break;
                    
                    case 'files_response':
                        if (message.data) {
                            console.log('Handling files response:', message.data);
                            handleFilesResponse(message.data);
                        }
                        break;
                    case 'user_facts_response':
                        if (message.data) {
                            console.log('Handling user facts response:', message.data);
                            handleUserFactsResponse(message.data);
                        }
                        break;
                    default:
                        console.log('Unknown recall message type:', message.type);
                }
            } catch (error) {
                console.error('Error processing Recall WebSocket message:', error);
                if (!(error instanceof SyntaxError)) {
                    addMessageToChat('status', 'Error processing recall server message. Please try again.');
                }
            }
        };
    }

    // Handle agent responses
    function handleAgentResponse(response) {
        if (!response || !response.agent_name || !response.answer) {
            console.warn('Invalid agent response format:', response);
            return;
        }

        // Use agent_name as the agentId
        const agentId = response.agent_name;

        // Generate a unique query ID if not provided
        const queryId = response.query_id || `q_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        // Add the agent's message to chat with the query ID
        const messageElement = addMessageToChat('agent', response.answer, agentId, null, queryId);

        // Add to appropriate history based on the source channel
        if (conversationHistory[currentAgentId]) {
            // Store the message with its query ID for later score updates
            const messageClone = messageElement.cloneNode(true);
            messageClone.setAttribute('data-query-id', queryId);
            conversationHistory[currentAgentId].push(messageClone);
        }

        // Scroll to bottom
        scrollToBottom();
    }

    // Handle quality updates
    function handleQualityUpdates(updates) {
        if (!updates || !Array.isArray(updates)) {
            console.warn('Invalid quality updates format:', updates);
            return;
        }

        console.log('Processing quality updates:', updates);

        updates.forEach(update => {
            if (!update.agent_name || update.response_score === undefined) {
                console.warn('Invalid quality update:', update);
                return;
            }

            console.log('Processing quality update for agent:', update.agent_name, 'score:', update.response_score);

            // Find the message using agent_name since query_id might be undefined
            const messages = document.querySelectorAll(`.agent-name[data-agent="${update.agent_name}"]`);
            if (messages.length === 0) {
                console.warn('Could not find message for agent:', update.agent_name);
                return;
            }

            // Get the last message from this agent
            const lastMessage = messages[messages.length - 1].closest('.message');
            if (!lastMessage) {
                console.warn('Could not find message element for agent:', update.agent_name);
                return;
            }

            console.log('Found message to update:', lastMessage);

            // Update the message opacity
            lastMessage.style.opacity = Math.max(0.4, update.response_score / 100);

            // Update the score dot
            const scoreDot = lastMessage.querySelector('.score-dot');
            if (scoreDot) {
                console.log('Updating score dot for message');
                // Remove all existing score classes
                scoreDot.classList.remove('blinking', 'score-100', 'score-0', 'score-other');
                scoreDot.className = 'score-dot';
                
                // Add the appropriate score class
                if (update.response_score >= 90) {
                    scoreDot.classList.add('score-100');
                } else if (update.response_score === 0) {
                    scoreDot.classList.add('score-0');
                } else {
                    scoreDot.classList.add('score-other');
                }
            } else {
                console.warn('Could not find score dot in message');
            }

            // Update the message in conversation history
            if (conversationHistory[currentAgentId]) {
                // Find the last message from this agent in the history
                const historyMessages = conversationHistory[currentAgentId].filter(
                    msg => msg.querySelector(`.agent-name[data-agent="${update.agent_name}"]`)
                );
                
                if (historyMessages.length > 0) {
                    const historyMessage = historyMessages[historyMessages.length - 1];
                    console.log('Updating message in conversation history');
                    const historyScoreDot = historyMessage.querySelector('.score-dot');
                    if (historyScoreDot) {
                        historyScoreDot.classList.remove('blinking', 'score-100', 'score-0', 'score-other');
                        historyScoreDot.className = 'score-dot';
                        if (update.response_score >= 90) {
                            historyScoreDot.classList.add('score-100');
                        } else if (update.response_score === 0) {
                            historyScoreDot.classList.add('score-0');
                        } else {
                            historyScoreDot.classList.add('score-other');
                        }
                    }
                } else {
                    console.warn('Could not find message in conversation history');
                }
            }
        });
    }

    // WebSocket connection management for WRITE operations (record submissions, file operations, user facts modifications)
    function connectRecordWebSocket() {
        if (recordWsConnection) {
            return;
        }
        
        const wsUrl = `${wsBaseUrl}/ws/record`;
        console.log('Connecting to Record WebSocket (WRITE operations):', wsUrl);
        
        recordWsConnection = new WebSocket(wsUrl);
        
        recordWsConnection.onopen = () => {
            console.log('Record WebSocket connection established');
            recordWsReconnectAttempts = 0;
        };
        
        recordWsConnection.onclose = () => {
            console.log('Record WebSocket connection closed');
            addMessageToChat('status', 'Connection lost. Please refresh the page to reconnect.');
            
            // Attempt to reconnect if under max attempts
            if (recordWsReconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                recordWsReconnectAttempts++;
                setTimeout(connectRecordWebSocket, 3000 * recordWsReconnectAttempts);
            }
        };
        
        recordWsConnection.onerror = (error) => {
            console.error('Record WebSocket error:', error);
            addMessageToChat('status', 'Connection error occurred. Attempting to reconnect...');
        };
        
        recordWsConnection.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                console.log('Received Record WebSocket message:', message);
                
                if (!message || !message.type) {
                    console.warn('Invalid record message format:', message);
                    return;
                }
                
                switch (message.type) {
                    case 'status_update':
                        if (message.data && message.data.message) {
                            // Only show status updates if there's no final response yet
                            if (!message.data.is_final) {
                                // Update the status message with the backend message
                                const existingStatus = document.querySelectorAll('.message.status');
                                existingStatus.forEach(msg => msg.remove());
                                addMessageToChat('status', message.data.message);
                            }
                        }
                        break;
                    case 'record_response':
                        if (message.data) {
                            handleRecordResponse(message.data);
                        }
                        break;
                    // Removed duplicate file_list_response case - using files_response consistently
                    // to match the backend's MessageType.FILES_RESPONSE enum value
                        break;
                    case 'files_response':
                        if (message.data) {
                            console.log('Handling files response:', message.data);
                            handleFilesResponse(message.data);
                        }
                        break;
                    case 'user_facts_response':
                        if (message.data) {
                            console.log('Handling user facts response:', message.data);
                            handleUserFactsResponse(message.data);
                        }
                        break;
                    default:
                        console.log('Unknown record message type:', message.type);
                }
            } catch (error) {
                console.error('Error processing Record WebSocket message:', error);
                if (!(error instanceof SyntaxError)) {
                    addMessageToChat('status', 'Error processing record server message. Please try again.');
                }
            }
        };
    }

    // Handle record operation responses
    function handleRecordResponse(response) {
        // Remove loading indicator
        removeLoadingIndicator();
        
        // Clear any existing status messages
        const existingStatus = document.querySelectorAll('.message.status');
        existingStatus.forEach(msg => msg.remove());
        
        // Check if this is a file text content update response
        if (response.file_id) {
            // This is a file text content update response
            if (response.success) {
                addMessageToChat('status', response.message || 'File content updated successfully.');
                // Refresh the file list to show updated status
                loadFileList();
                // Close the edit modal if it's open
                const modal = document.getElementById('textContentModal');
                if (modal && modal.style.display === 'block') {
                    modal.style.display = 'none';
                }
            } else {
                addMessageToChat('status', `Error: ${response.message || 'Failed to update file content.'}`);
            }
        } else {
            // This is a regular record submission response
            if (response.success) {
                // Add a persistent system message to the chat
                const messageElement = addMessageToChat('agent', response.message || 'Record submitted successfully.', 'system');
                
                // Add to appropriate history
                recordHistory[currentRecordType].push(messageElement);
            } else {
                // Handle error case with a persistent error message
                addMessageToChat('agent', `Error: ${response.message || 'Failed to submit record.'}`, 'system');
            }
        }
        
        // Scroll to bottom
        scrollToBottom();
    }

    // Handle files-related responses from WebSocket connections
    function handleFilesResponse(response) {
        console.log('Processing files response:', response);
        
        // Remove any loading indicators
        removeLoadingIndicator();
        
        if (response.success) {
            // Check if this is a list response with files array
            if (response.files && Array.isArray(response.files)) {
                console.log('File list received, displaying', response.files.length, 'files');
                displayFileList(response.files);
            } 
            // Check if this is a delete response
            else if (response.message && response.message.includes('deleted')) {
                console.log('File deletion successful');
                addMessageToChat('status', response.message || 'File operation completed successfully');
                // Refresh the file list after deletion
                loadFileList();
            }
            // Other successful file operations
            else {
                addMessageToChat('status', response.message || 'File operation completed successfully');
            }
        } else {
            // Handle failed file operations
            const errorMsg = response.message || 'Error processing file operation';
            console.error('File operation error:', errorMsg);
            addMessageToChat('error', errorMsg);
        }
    }
    
    // Handle user facts responses from WebSocket connections
    function handleUserFactsResponse(response) {
        console.log('Processing user facts response:', response);
        
        // Remove any loading indicators
        removeLoadingIndicator();
        
        if (response.success) {
            // Check if this is a list response with facts array
            if (response.facts && Array.isArray(response.facts)) {
                console.log('User facts list received, displaying', response.facts.length, 'facts');
                // Store the facts globally
                userFacts = response.facts;
                // Display the facts (which uses the currentCategory filter)
                displayUserFacts(userFacts);
            } 
            // Individual fact response
            else if (response.fact) {
                console.log('User fact operation successful:', response.fact);
                addMessageToChat('status', response.message || 'User fact operation completed successfully');
                // Refresh user facts
                loadUserFacts();
            }
            // Other successful operations
            else {
                addMessageToChat('status', response.message || 'User fact operation completed successfully');
                // Refresh user facts list if it was a delete operation
                if (response.message && response.message.includes('deleted')) {
                    loadUserFacts();
                }
            }
        } else {
            // Handle failed operations
            const errorMsg = response.message || 'Error processing user fact operation';
            console.error('User fact operation error:', errorMsg);
            addMessageToChat('error', errorMsg);
        }
    }
    
    // Generate a unique query ID
    function generateQueryId() {
        return 'q_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Update handleSendMessage function to use WebSocket for record operations
    async function handleSendMessage() {
        const text = userInput.value.trim();
        
        if (!text && !selectedFile) {
            return;
        }
        
        // Determine if this is a record or recall operation
        const isRecallOperation = currentMode === 'recall';
        
        // Generate a query ID for this message
        const queryId = generateQueryId();
        
        // Add user message to chat
        const userMessageElement = addMessageToChat('user', text, null, null, queryId);
        
        // Add to appropriate history
        if (currentMode === 'recall') {
            if (conversationHistory[currentAgentId]) {
                conversationHistory[currentAgentId].push(userMessageElement.cloneNode(true));
            }
        } else {
            recordHistory[currentRecordType].push(userMessageElement.cloneNode(true));
        }
        
        // Clear input
        userInput.value = '';
        
        // Handle file attachment for Butterfly agent
        let attachmentFilePath = null;
        
        try {
            if (isRecallOperation && currentAgentId === 'butterfly' && selectedFile) {
                // Show status message for upload
                const statusMsg = addMessageToChat('status', `Uploading ${selectedFile.type.startsWith('image/') ? 'image' : 'video'} for social media post...`);
                
                // Upload the file
                const uploadResult = await uploadFileForSocialMedia(selectedFile, userId);
                
                // Remove the status message
                statusMsg.remove();
                
                if (!uploadResult.success) {
                    addMessageToChat('agent', `Failed to upload file: ${uploadResult.message}`, 'system');
                    removeSelectedFile();
                    return;
                }
                
                // Store the file path for later use
                attachmentFilePath = uploadResult.filePath;
                
                // Show confirmation of upload
                addMessageToChat('agent', `File uploaded successfully and will be used in your post.`, 'system');
            }
        
            if (isRecallOperation) {
                // Ensure WebSocket connection is established for recall
                if (!recallWsConnection || recallWsConnection.readyState !== WebSocket.OPEN) {
                    connectRecallWebSocket();
                    // Wait for connection to be established
                    await new Promise((resolve, reject) => {
                        const timeout = setTimeout(() => {
                            reject(new Error('Recall WebSocket connection timeout'));
                        }, 5000);
                        
                        const checkConnection = setInterval(() => {
                            if (recallWsConnection && recallWsConnection.readyState === WebSocket.OPEN) {
                                clearTimeout(timeout);
                                clearInterval(checkConnection);
                                resolve();
                            }
                        }, 100);
                    });
                }
                
                // Clear any existing status messages
                const existingStatus = document.querySelectorAll('.message.status');
                existingStatus.forEach(msg => msg.remove());
                
                // Prepare the recall message with internal agent name
                const recallMessage = {
                    type: 'recall_query',
                    data: {
                        query: text,
                        user_id: userId,
                        target_agent: currentAgentId,
                        query_id: queryId
                    }
                };
                
                // Add attachment path for Butterfly agent if available
                if (currentAgentId === 'butterfly' && attachmentFilePath) {
                    recallMessage.data.attachment_file_path = attachmentFilePath;
                    console.log('Adding attachment to message:', attachmentFilePath);
                }
                
                console.log("Sending recall message:", recallMessage);
                recallWsConnection.send(JSON.stringify(recallMessage));
                
                // Clean up the file selection after sending
                if (selectedFile) {
                    removeSelectedFile();
                }
                
                return;
            }
            
            // Handle record operation
            // Ensure WebSocket connection is established for record
            if (!recordWsConnection || recordWsConnection.readyState !== WebSocket.OPEN) {
                connectRecordWebSocket();
                // Wait for connection to be established
                await new Promise((resolve, reject) => {
                    const timeout = setTimeout(() => {
                        reject(new Error('Record WebSocket connection timeout'));
                    }, 5000);
                    
                    const checkConnection = setInterval(() => {
                        if (recordWsConnection && recordWsConnection.readyState === WebSocket.OPEN) {
                            clearTimeout(timeout);
                            clearInterval(checkConnection);
                            resolve();
                        }
                    }, 100);
                });
            }
            
            // Clear any existing status messages
            const existingStatus = document.querySelectorAll('.message.status');
            existingStatus.forEach(msg => msg.remove());
            
            // Prepare the record submission message
            const recordMessage = {
                type: "record_submission",  // Using lowercase to match backend enum
                data: {
                    content: text,
                    user_id: userId,
                    record_type: currentRecordType,
                    metadata: {
                        timestamp: new Date().toISOString()
                    }
                }
            };
            
            console.log("Sending record message:", recordMessage);
            recordWsConnection.send(JSON.stringify(recordMessage));
            
            // Clean up the file selection after sending
            if (selectedFile) {
                removeSelectedFile();
            }
            
        } catch (error) {
            console.error('Error in handleSendMessage:', error);
            removeLoadingIndicator();
            addMessageToChat('agent', `Error: ${error.message}. Please try again.`, 'system');
            
            // Clean up the file selection on error
            if (selectedFile) {
                removeSelectedFile();
            }
        }
    }

    // File Management Functions
    function initFileManagement() {
        const fileUploadContainer = document.querySelector('.file-upload-container');
        
        // Click handler for the upload button
        fileUploadButton.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent container's click event
            fileUploadInput.click();
        });
        
        // Click handler for the container
        fileUploadContainer.addEventListener('click', () => {
            fileUploadInput.click();
        });
        
        // File input change handler
        fileUploadInput.addEventListener('change', handleFileUpload);
        
        // Drag and drop handlers
        fileUploadContainer.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileUploadContainer.classList.add('drag-over');
        });
        
        fileUploadContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileUploadContainer.classList.add('drag-over');
        });
        
        fileUploadContainer.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileUploadContainer.classList.remove('drag-over');
        });
        
        fileUploadContainer.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileUploadContainer.classList.remove('drag-over');
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                handleFilesUpload(files);
            }
        });
        
        // Other file management event listeners
        refreshFileList.addEventListener('click', loadFileList);
        deleteSelectedFiles.addEventListener('click', deleteFiles);
    }

    async function handleFileUpload(e) {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            handleFilesUpload(files);
        }
    }

    async function handleFilesUpload(files) {
        const formData = new FormData();
        files.forEach(file => {
            console.log('Uploading file:', file.name, 'MIME type:', file.type);
            formData.append('files', file);
        });
        formData.append('user_id', userId);

        try {
            const response = await fetch(`${apiBaseUrl}/files/upload`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            if (result.success) {
                // Clear the file input
                fileUploadInput.value = '';
                // Refresh the file list
                loadFileList();
                // Show success message
                addMessageToChat('status', `Successfully uploaded ${result.file_ids.length} files.`);
            } else {
                // Handle file conflicts
                if (result.message.includes('file already exists')) {
                    const shouldOverwrite = confirm('Some files already exist. Would you like to overwrite them?');
                    if (shouldOverwrite) {
                        // Retry upload with overwrite flag
                        formData.append('overwrite', 'true');
                        const retryResponse = await fetch(`${apiBaseUrl}/files/upload`, {
                            method: 'POST',
                            body: formData
                        });
                        const retryResult = await retryResponse.json();
                        if (retryResult.success) {
                            addMessageToChat('status', `Successfully uploaded ${retryResult.file_ids.length} files.`);
                            loadFileList();
                        }
                    } else {
                        addMessageToChat('status', 'File upload cancelled. Existing files were not overwritten.');
                    }
                } else {
                    addMessageToChat('status', `Error uploading files: ${result.message}`);
                }
            }
        } catch (error) {
            console.error('Error uploading files:', error);
            addMessageToChat('status', 'Error uploading files. Please try again.');
        }
    }

    function loadFileList() {
        // Ensure recall WebSocket is connected
        if (!recallWsConnection || recallWsConnection.readyState !== WebSocket.OPEN) {
            connectRecallWebSocket();
            setTimeout(loadFileList, 1000); // Try again after connection is established
            return;
        }
        
        try {
            // Create a loading indicator
            addMessageToChat('status', 'Loading files...');
            
            // Create a unique ID for this request
            const requestId = generateQueryId();
            
            // Send the request through WebSocket
            // Use files_list to match backend's MessageType enum
            recallWsConnection.send(JSON.stringify({
                type: "files_list",  // Match the backend's MessageType enum
                request_id: requestId,
                data: {
                    user_id: userId
                }
            }));
            
            console.log('Sent file list request via WebSocket with type: files_list');
        } catch (error) {
            console.error('Error loading files via WebSocket:', error);
            addMessageToChat('status', 'Error loading files. Please try again.');
        }
    }

    function displayFileList(files) {
        fileList.innerHTML = '';
        selectedFiles.clear();
        deleteSelectedFiles.disabled = true;

        files.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.dataset.fileId = file.id;

            const fileIcon = getFileIcon(file.file_type, file.file_name);
            const fileSize = formatFileSize(file.file_size);
            const uploadDate = formatDateTimeForDisplay(new Date(file.upload_date));

            // Map status to display text and class
            let statusText, statusClass;
            switch (file.processing_status) {
                case 'pending':
                    statusText = 'Pending';
                    statusClass = 'pending';
                    break;
                case 'processing':
                    statusText = 'Processing';
                    statusClass = 'processing';
                    break;
                case 'complete':
                    statusText = 'Complete';
                    statusClass = 'complete';
                    break;
                case 'error':
                    statusText = 'Error';
                    statusClass = 'error';
                    break;
                default:
                    statusText = capitalizeFirstLetter(file.processing_status);
                    statusClass = file.processing_status;
            }

            // Check if file has text content that can be edited (both transcribed and complete status)
            console.log('File processing status:', file.processing_status);
            const hasTextContent = file.text_content && (file.processing_status === 'transcribed' || file.processing_status === 'complete');

            fileItem.innerHTML = `
                <input type="checkbox" class="file-checkbox" data-file-id="${file.id}">
                <div class="file-icon">
                    <i class="${fileIcon}"></i>
                </div>
                <div class="file-info">
                    <div class="file-name">${file.file_name}</div>
                    <div class="file-details">
                        ${fileSize} • Uploaded ${uploadDate}
                    </div>
                </div>
                <div class="file-status ${statusClass}">
                    ${statusText}
                </div>
                <div class="file-actions">
                    <button class="file-action-button view" data-file-id="${file.id}" ${!hasTextContent ? 'disabled' : ''}>
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="file-action-button delete" data-file-id="${file.id}">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;

            // Add event listeners
            const checkbox = fileItem.querySelector('.file-checkbox');
            checkbox.addEventListener('change', () => {
                if (checkbox.checked) {
                    selectedFiles.add(file.id);
                    fileItem.classList.add('selected');
                } else {
                    selectedFiles.delete(file.id);
                    fileItem.classList.remove('selected');
                }
                deleteSelectedFiles.disabled = selectedFiles.size === 0;
            });

            const deleteButton = fileItem.querySelector('.file-action-button.delete');
            deleteButton.addEventListener('click', () => deleteFile(file.id));

            const viewButton = fileItem.querySelector('.file-action-button.view');
            if (!viewButton.disabled) {
                viewButton.addEventListener('click', () => openTextContentModal(file));
            }

            fileList.appendChild(fileItem);
        });
    }

    async function deleteFiles() {
        if (selectedFiles.size === 0) return;

        const confirmed = confirm(`Are you sure you want to delete ${selectedFiles.size} file(s)?`);
        if (!confirmed) return;

        const deletePromises = Array.from(selectedFiles).map(fileId => 
            fetch(`${apiBaseUrl}/files/${fileId}?user_id=${userId}`, {
                method: 'DELETE'
            })
        );

        try {
            const results = await Promise.allSettled(deletePromises);
            const successCount = results.filter(r => r.status === 'fulfilled').length;
            
            if (successCount > 0) {
                addMessageToChat('status', `Successfully deleted ${successCount} file(s).`);
                loadFileList();
            }
        } catch (error) {
            console.error('Error deleting files:', error);
            addMessageToChat('status', 'Error deleting files. Please try again.');
        }
    }

    function deleteFile(fileId) {
        const confirmed = confirm('Are you sure you want to delete this file?');
        if (!confirmed) return;

        // Ensure record WebSocket is connected
        if (!recordWsConnection || recordWsConnection.readyState !== WebSocket.OPEN) {
            connectRecordWebSocket();
            setTimeout(() => deleteFile(fileId), 1000); // Try again after connection is established
            return;
        }

        try {
            // Create a loading indicator
            addMessageToChat('status', 'Deleting file...');
            
            // Create a unique ID for this request
            const requestId = generateQueryId();
            
            // Send the delete request through WebSocket
            recordWsConnection.send(JSON.stringify({
                type: "files_delete",  // Using lowercase to match backend enum
                request_id: requestId,
                data: {
                    user_id: userId,
                    file_id: fileId
                }
            }));
            
            console.log('Sent file deletion request via WebSocket with type: files_delete');
        } catch (error) {
            console.error('Error deleting file via WebSocket:', error);
            addMessageToChat('status', 'Error deleting file. Please try again.');
        }
    }

    function getFileIcon(fileType, fileName) {
        // First check by file extension
        if (fileName) {
            const extension = fileName.split('.').pop().toLowerCase();
            const extensionIconMap = {
                'pdf': 'fas fa-file-pdf',
                'doc': 'fas fa-file-word',
                'docx': 'fas fa-file-word',
                'csv': 'fas fa-file-csv',
                'json': 'fas fa-file-code',
                'md': 'fas fa-file-code',  // Use code icon for markdown files
                'txt': 'fas fa-file-alt',
                'text': 'fas fa-file-alt'
            };
            
            if (extensionIconMap[extension]) {
                return extensionIconMap[extension];
            }
        }
        
        // Fallback to MIME type
        const mimeIconMap = {
            'text/plain': 'fas fa-file-alt',
            'application/pdf': 'fas fa-file-pdf',
            'application/msword': 'fas fa-file-word',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'fas fa-file-word',
            'text/csv': 'fas fa-file-csv',
            'application/json': 'fas fa-file-code',
            'text/markdown': 'fas fa-file-code',  // Use code icon for markdown files
            'text/x-markdown': 'fas fa-file-code'
        };
        
        return mimeIconMap[fileType] || 'fas fa-file';
    }

    function formatDateTimeForDisplay(date) {
        // Format: '26 Mar 2025 18:30:30' to match backend DISPLAY_DATETIME_FORMAT
        const day = date.getDate().toString().padStart(2, '0');
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const month = monthNames[date.getMonth()];
        const year = date.getFullYear();
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        const seconds = date.getSeconds().toString().padStart(2, '0');
        
        return `${day} ${month} ${year} ${hours}:${minutes}:${seconds}`;
    }

    // Text content modal functionality
    function openTextContentModal(file) {
        const modal = document.getElementById('textContentModal');
        const textArea = document.getElementById('textContentArea');
        const saveButton = document.getElementById('saveTextContent');
        const cancelButton = document.getElementById('cancelTextContent');
        const closeButton = modal.querySelector('.close-modal');
        
        // Set the current file ID as a data attribute on the modal
        modal.dataset.fileId = file.id;
        
        // Set the text content in the textarea
        textArea.value = file.text_content || '';
        
        // Disable save button initially
        saveButton.disabled = true;
        
        // Show the modal
        modal.style.display = 'block';
        
        // Event listeners
        textArea.addEventListener('input', function() {
            // Enable save button if text has changed
            saveButton.disabled = false;
        });
        
        const closeModal = function() {
            modal.style.display = 'none';
            // Remove event listeners to prevent memory leaks
            textArea.removeEventListener('input', null);
        };
        
        closeButton.addEventListener('click', closeModal);
        cancelButton.addEventListener('click', closeModal);
        
        saveButton.addEventListener('click', async function() {
            const fileId = modal.dataset.fileId;
            const newTextContent = textArea.value;
            try {
                await updateFileTextContent(fileId, newTextContent);
                // Don't close the modal immediately - it will be closed when we receive a successful response
            } catch (error) {
                console.error('Error in save button click handler:', error);
                addMessageToChat('status', 'Error updating file content. Please try again.');
            }
        });
        
        // Close if clicking outside the modal content
        window.addEventListener('click', function(event) {
            if (event.target === modal) {
                closeModal();
            }
        });
    }
    
    async function updateFileTextContent(fileId, textContent) {
        try {
            // Make sure we have a record WebSocket connection
            if (!recordWsConnection || recordWsConnection.readyState !== WebSocket.OPEN) {
                connectRecordWebSocket();
                
                // Wait for the connection to be established
                if (recordWsConnection.readyState === WebSocket.CONNECTING) {
                    console.log('Waiting for Record WebSocket connection to be established...');
                    await new Promise((resolve, reject) => {
                        const timeout = setTimeout(() => {
                            reject(new Error('Timed out waiting for WebSocket connection'));
                        }, 5000);
                        
                        const checkConnection = () => {
                            if (recordWsConnection.readyState === WebSocket.OPEN) {
                                clearTimeout(timeout);
                                resolve();
                            } else if (recordWsConnection.readyState === WebSocket.CLOSED || 
                                      recordWsConnection.readyState === WebSocket.CLOSING) {
                                clearTimeout(timeout);
                                reject(new Error('WebSocket connection closed'));
                            } else {
                                setTimeout(checkConnection, 100);
                            }
                        };
                        
                        checkConnection();
                    });
                }
            }
            
            // Prepare the message to send
            const message = {
                type: "record_update_text",  // Using lowercase to match backend enum
                data: {
                    file_id: fileId,
                    user_id: userId,
                    text_content: textContent
                }
            };
            
            // Send the update message via WebSocket
            recordWsConnection.send(JSON.stringify(message));
            
            // The response will be handled by the WebSocket message handler
            console.log('Sent file text content update request via Record WebSocket with type: record_update_text');
            
            // Show a temporary status message
            addMessageToChat('status', 'Updating file content...');
            
        } catch (error) {
            console.error('Error updating file content:', error);
            addMessageToChat('status', 'Error updating file content. Please try again.');
        }
    }
    
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function switchChannel(channel) {
        // Clear the current chat messages
        chatMessages.innerHTML = '';
        
        // Hide all interfaces
        document.querySelectorAll('.interface').forEach(interface => {
            interface.style.display = 'none';
        });
        
        // Show the appropriate interface
        if (channel === 'files') {
            fileManagementInterface.style.display = 'block';
            // Load file list
            loadFileList();
        } else {
            // Show chat interface
            chatInterface.style.display = 'block';
            
            // Update current agent
            currentAgentId = channel;
            
            // Update UI elements
            updateCurrentChatInfo(channel);
            
            // Display conversation history for the selected channel
            displayConversationHistory(channel);
        }
        
        // Update active state in sidebar
        document.querySelectorAll('.sidebar-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.channel === channel) {
                item.classList.add('active');
            }
        });
    }

    // Add CSS for status message styling
    const style = document.createElement('style');
    style.textContent = `
        .message.status {
            background: none;
            margin: 0.5rem auto;
            max-width: 90%;
            text-align: left;
            font-size: 0.9rem;
            color: var(--light-text);
            display: flex;
            align-items: center;
            padding: 0.5rem;
        }

        .message.status .message-content {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #666;
        }

        .loading-dots {
            display: inline-flex;
            gap: 4px;
            margin-right: 8px;
        }

        .loading-dots span {
            width: 4px;
            height: 4px;
            background: #666;
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }

        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }
        .loading-dots span:nth-child(3) { animation-delay: 0s; }

        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        /* Score dot styles */
        .score-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
            transition: background-color 0.3s ease;
        }

        .score-dot.blinking {
            background-color: #FFC107;  /* Yellow */
            animation: blink 1s infinite;
        }

        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }

        .score-dot.score-100 {
            background-color: #4CAF50;  /* Green */
            animation: none;
        }

        .score-dot.score-0 {
            background-color: #F44336;  /* Red */
            animation: none;
        }

        .score-dot.score-other {
            background-color: #FFC107;  /* Yellow */
            animation: none;
        }
    `;
    document.head.appendChild(style);

    // Function to upload a file for social media
    async function uploadFileForSocialMedia(file, userId) {
        console.log('Uploading file for social media:', file.name);
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('user_id', userId);

        try {
            const response = await fetch(`${apiBaseUrl}/social_media/upload`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            console.log('Social media upload response:', result);
            
            if (!result.success) {
                console.error('File upload failed:', result.message);
                return { success: false, message: result.message };
            }
            
            if (!result.file_ids || result.file_ids.length === 0) {
                console.error('File upload returned no file path');
                return { success: false, message: 'No file path returned from server' };
            }
            
            const filePath = result.file_ids[0]; // The backend returns the full file path
            console.log('File uploaded successfully, path:', filePath);
            
            return { 
                success: true, 
                filePath: filePath,
                message: result.message 
            };
        } catch (error) {
            console.error('Error uploading file:', error);
            return { 
                success: false, 
                message: error.message || 'Network error while uploading file'
            };
        }
    }
}); 