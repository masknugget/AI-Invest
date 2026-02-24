const fetchStreamData = async (prompt) => {
    const response = await fetch('http://localhost:8000/api/chatbot/chat/completions', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer YOUR_API_KEY`
        },
        body: JSON.stringify( {
            "messages": [
                {"role": "user", "content": "你好，请介绍一下你自己"}
            ],
            "stream": true
        })
    });
    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    const reader = response.body.getReader();

    const decoder = new TextDecoder('utf-8');
    let done = false;
    while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        const chunk = decoder.decode(value, { stream: true });
        console.log(chunk);

    }
};

fetchStreamData("");