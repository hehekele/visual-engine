export default defineBackground(() => {
  console.log('[Visual Generator] Background service worker active');

  // Handle messages from content scripts
  browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'API_REQUEST') {
      const { url, options } = message;
      
      // Perform the fetch in the background context
      fetch(url, options)
        .then(async (response) => {
          const data = await response.json();
          sendResponse({ success: true, data });
        })
        .catch((error) => {
          console.error('[Background Fetch Error]', error);
          sendResponse({ success: false, error: error.message });
        });
      
      return true; // Keep the message channel open for async response
    }
  });
});
