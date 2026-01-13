export default defineContentScript({
  matches: ['https://image.baidu.com/*'],
  main() {
    console.log('Baidu Extension Loaded');
    
    // 1. Floating Logo
    addFloatingLogo();

    // 2. Image Buttons
    handleImages();
    
    // Observer for dynamic content
    const observer = new MutationObserver((mutations) => {
      // Debounce or just run? For simplicity, just run.
      // Ideally check if nodes were added.
      let shouldUpdate = false;
      for (const mutation of mutations) {
        if (mutation.addedNodes.length > 0) {
          shouldUpdate = true;
          break;
        }
      }
      if (shouldUpdate) {
        handleImages();
      }
    });
    
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  },
});

function addFloatingLogo() {
  if (document.getElementById('wxt-floating-logo')) return;
  
  const logo = document.createElement('div');
  logo.id = 'wxt-floating-logo';
  logo.innerText = '衡哲AI';
  Object.assign(logo.style, {
    position: 'fixed',
    top: '100px',
    right: '60px',
    width: '60px',
    height: '60px',
    borderRadius: '50%',
    backgroundColor: '#4e54c8',
    color: 'white',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: '2147483647',
    boxShadow: '0 4px 15px rgba(0,0,0,0.3)',
    cursor: 'default',
    fontFamily: 'Arial, sans-serif',
    fontWeight: 'bold',
    userSelect: 'none',
    pointerEvents: 'auto',
    fontSize: '12px'
  });
  
  document.body.appendChild(logo);
}

function handleImages() {
  const images = document.querySelectorAll('img');
  
  images.forEach((img) => {
    // Type guard for HTMLImageElement
    if (!(img instanceof HTMLImageElement)) return;

    // Skip small images/icons
    // Adjust logic to be more permissive if needed, but 50x50 filters out most icons
    if ((img.width < 200 && img.height < 200) || (img.naturalWidth > 0 && img.naturalWidth < 200)) return;
    
    // Check if already processed
    if (img.dataset.wxtProcessed) return;
    
    // Find a suitable parent to attach the button
    const parent = img.parentElement;
    if (!parent) return;
    
    // Mark as processed
    img.dataset.wxtProcessed = 'true';
    
    // Ensure parent position is relative for absolute positioning of the button
    const style = window.getComputedStyle(parent);
    if (style.position === 'static') {
      parent.style.position = 'relative';
    }
    
    // Create Button
    const btn = document.createElement('button');
    btn.innerText = '抓取信息';
    btn.className = 'wxt-capture-btn';
    Object.assign(btn.style, {
      position: 'absolute',
      top: '5px',
      left: '5px',
      zIndex: '100',
      padding: '4px 8px',
      fontSize: '12px',
      backgroundColor: 'rgba(78,84,200, 1)',
      color: 'white',
      border: 'none',
      borderRadius: '4px',
      cursor: 'pointer',
      opacity: '0.8',
      transition: 'opacity 0.2s'
    });
    
    btn.addEventListener('mouseenter', () => {
      btn.style.opacity = '1';
    });
    
    btn.addEventListener('mouseleave', () => {
      btn.style.opacity = '0.8';
    });
    
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      showImageInfo(img);
    });
    
    parent.appendChild(btn);
  });
}

function showImageInfo(img: HTMLImageElement) {
  // Use sendMessage to get info from background (demonstrating background script usage)
  browser.runtime.sendMessage({
    type: 'BAIDU_TASK',
    action: 'ANALYZE_IMAGE',
    payload: {
      src: img.src,
      width: img.naturalWidth,
      height: img.naturalHeight
    }
  }).then((response) => {
    // Render modal with response from background
    renderModal(img, response);
  }).catch((err) => {
    console.error('Error talking to background:', err);
    // Fallback if background fails
    renderModal(img, { backgroundInfo: 'Background script not reachable' });
  });
}

function renderModal(img: HTMLImageElement, backgroundData: any) {
  console.log('Rendering modal with data:', backgroundData);
  // Remove existing modal if any
  const existing = document.getElementById('wxt-info-modal');
  if (existing) existing.remove();
  
  const modal = document.createElement('div');
  modal.id = 'wxt-info-modal';
  
  // Styles for the modal overlay
  Object.assign(modal.style, {
    position: 'fixed',
    top: '0',
    left: '0',
    width: '100vw',
    height: '100vh',
    backgroundColor: 'rgba(0,0,0,0.5)',
    zIndex: '2147483647',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  });
  
  const content = document.createElement('div');
  Object.assign(content.style, {
    backgroundColor: 'white',
    padding: '25px',
    borderRadius: '12px',
    maxWidth: '500px',
    width: '90%',
    boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
    fontFamily: 'Segoe UI, Roboto, Helvetica, Arial, sans-serif',
    color: '#333'
  });
  
  const title = document.createElement('h3');
  title.innerText = '图片信息';
  title.style.marginTop = '0';
  title.style.marginBottom = '20px';
  title.style.borderBottom = '1px solid #eee';
  title.style.paddingBottom = '10px';
  
  const infoList = document.createElement('div');
  infoList.style.fontSize = '14px';
  
  const addInfo = (label: string, value: string) => {
    const row = document.createElement('div');
    row.style.marginBottom = '12px';
    row.style.display = 'flex';
    row.style.alignItems = 'flex-start';
    
    const labelSpan = document.createElement('span');
    labelSpan.innerText = label + ': ';
    labelSpan.style.fontWeight = 'bold';
    labelSpan.style.width = '80px'; // Increased width for longer labels
    labelSpan.style.flexShrink = '0';
    
    const valueSpan = document.createElement('span');
    valueSpan.innerText = value;
    valueSpan.style.wordBreak = 'break-all';
    valueSpan.style.color = '#555';
    
    row.appendChild(labelSpan);
    row.appendChild(valueSpan);
    infoList.appendChild(row);
  };
  
  addInfo('尺寸', `${img.naturalWidth} x ${img.naturalHeight}`);
  addInfo('描述', img.alt || '无');
  addInfo('URL', img.src);
  if (backgroundData && backgroundData.backgroundInfo) {
    addInfo('后台反馈', backgroundData.backgroundInfo);
  }
  if (backgroundData && backgroundData.processedAt) {
    addInfo('处理时间', backgroundData.processedAt);
  }
  
  const btnContainer = document.createElement('div');
  btnContainer.style.display = 'flex';
  btnContainer.style.justifyContent = 'flex-end';
  btnContainer.style.marginTop = '20px';
  
  const closeBtn = document.createElement('button');
  closeBtn.innerText = '关闭';
  Object.assign(closeBtn.style, {
    padding: '8px 20px',
    backgroundColor: '#4e54c8',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '14px'
  });
  closeBtn.onclick = () => modal.remove();
  
  btnContainer.appendChild(closeBtn);
  content.appendChild(title);
  content.appendChild(infoList);
  content.appendChild(btnContainer);
  modal.appendChild(content);
  
  modal.onclick = (e) => {
    if (e.target === modal) modal.remove();
  };
  
  document.body.appendChild(modal);
}
