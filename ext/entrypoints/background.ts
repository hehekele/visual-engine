import { handleBaiduTask } from '../services/baiduService';
import { handleAliexpressTask } from '../services/aliexpressService';

export default defineBackground(() => {
  console.log('Hello background! browser.runtime.id =', browser.runtime.id);

  // Listen for messages from content script
  browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // console.log(sender);
    console.log(`Background received message [${message.type}]:`, message);

    // 路由分发逻辑
    switch (message.type) {
      case 'BAIDU_TASK':
        // 处理百度相关逻辑
        const baiduResponse = handleBaiduTask(message);
        sendResponse(baiduResponse);
        break;

      case 'ALIEXPRESS_TASK':
        // 处理速卖通相关逻辑
        const aliResponse = handleAliexpressTask(message);
        sendResponse(aliResponse);
        break;

      case 'IXSPY_LOGIN':
        handleIxSpyLogin(message.payload)
          .then(res => sendResponse(res))
          .catch(err => sendResponse({ success: false, error: err.message }));
        return true;

      case 'IXSPY_FETCH_INFO':
        handleIxSpyFetchInfo(message.payload)
          .then(res => sendResponse(res))
          .catch(err => sendResponse({ success: false, error: err.message }));
        return true;

      default:
        console.warn('Unknown message type:', message.type);
    }

    // Return true to indicate we will send a response asynchronously (if needed)
    // Even for sync responses, it's often safer to return true if you might change to async later,
    // but strict typing might complain if not actually async. 
    // Here we are synchronous for now, but keeping it true allows flexibility.
    return true;
  });
});

async function handleIxSpyLogin(payload: any) {
  try {
    const { username, password } = payload;
    const response = await fetch('https://user.ixspy.com/login', {
      method: 'POST',
      headers: {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        "user_name_email": username,
        "password": password,
        "site": "7",
        "toUrl": "https://ixspy.com/data",
        "redirectUrl": "https://ixspy.com/login",
        "ext_url": ""
      })
    });
    
    if (response.ok) {
        return { success: true };
    }
    return { success: false, status: response.status };
  } catch (e: any) {
    console.error('IxSpy login failed', e);
    return { success: false, error: e.message };
  }
}

async function handleIxSpyFetchInfo(payload: any) {
  try {
    const { id } = payload;
    const response = await fetch('https://ixspy.com/goods-info', {
        method: 'POST',
        headers: {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json;charset=UTF-8',
        },
        body: JSON.stringify({ id: id })
    });
    
    if (response.ok) {
        const json = await response.json();
        return { success: true, data: json.data };
    } else {
        if (response.status === 401 || response.status === 403) {
             return { success: false, error: 'Unauthorized' };
        }
        return { success: false, status: response.status };
    }
  } catch (e: any) {
    console.error('IxSpy fetch info failed', e);
    return { success: false, error: e.message };
  }
}
