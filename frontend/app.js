async function search() {
    const freeText = document.getElementById('freeText').value.trim();
    // Keyword and Category inputs are removed. Defaulting to 'all' for category.
    const category = 'all';

    if (!freeText) {
        alert("会社概要・ニーズを入力してください");
        return;
    }

    const loading = document.getElementById('loading');
    const tbody = document.querySelector('#resultsTable tbody');

    const now = new Date();
    const timeStr = now.toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' });


    loading.style.display = 'block';
    const loadingText = document.getElementById('loadingText');
    if (loadingText) {
        loadingText.innerText = `[${timeStr}] AIが分析中... (これには時間がかかります)`;
    }

    tbody.innerHTML = ''; // Clear previous results

    try {
        const url = new URL('http://localhost:8004/api/v1/bids');
        // Keyword 'q' is no longer used
        url.searchParams.append('category', category);
        if (freeText) url.searchParams.append('free_text', freeText);

        // Collect selected sources
        const sources = [];
        if (document.getElementById('sourceGov').checked) sources.push('gov');
        if (document.getElementById('sourceTokyo').checked) sources.push('tokyo');
        if (document.getElementById('sourceKanagawa').checked) sources.push('kanagawa');

        if (sources.length > 0) {
            url.searchParams.append('sources', sources.join(','));
        } else {
            alert("検索対象を少なくとも1つ選択してください");
            return;
        }

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Search failed');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        const logList = document.getElementById('logList');
        const searchLogs = document.getElementById('searchLogs');

        logList.innerHTML = '';
        searchLogs.style.display = 'block';

        let finalResults = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep the last incomplete line

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const event = JSON.parse(line);
                    if (event.type === 'log') {
                        // Update loading text for immediate feedback

                        // Add to log list
                        const li = document.createElement('li');
                        li.innerHTML = `・${event.message}`;
                        li.style.marginBottom = '5px';
                        logList.appendChild(li);
                        // Auto-scroll to bottom of logs
                    } else if (event.type === 'result') {
                        finalResults = event.data;
                    }
                } catch (e) {
                    console.error('Error parsing JSON line:', e);
                }
            }
        }

        if (finalResults.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6">結果が見つかりませんでした</td></tr>';
        } else {
            finalResults.forEach(item => {
                const row = document.createElement('tr');

                // Check if expired
                let isExpired = false;
                if (item.deadline) {
                    const deadlineDate = new Date(item.deadline);
                    const now = new Date();
                    if (deadlineDate < now) {
                        isExpired = true;
                    }
                }

                if (isExpired) {
                    row.style.color = '#aaa';
                    row.style.backgroundColor = '#f0f0f0';
                }

                row.innerHTML = `
                    <td>${item.title}</td>
                    <td>${item.organization}</td>
                    <td>
                        ${item.deadline || '-'}
                        ${isExpired ? '<br><span style="color: red; font-weight: bold; font-size: 0.8em;">受付終了</span>' : ''}
                    </td>
                    <td>${item.category}</td>
                    <td>${item.source}</td>
                    <td><a href="${item.url}" target="_blank" style="${isExpired ? 'color: #aaa;' : ''}">詳細</a></td>
                `;
                tbody.appendChild(row);
            });
        }

    } catch (error) {
        console.error('Error:', error);
        alert('検索中にエラーが発生しました');
    } finally {
        loading.style.display = 'none';
    }
}
