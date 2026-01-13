export interface Product {
  id: string;
  images: string[];
  title: string;
  info: string;
  url: string;
  rating: string | null;
  soldCount: string | null;
  reviewCount: string;
  add_date?: string;
}

export const autoScroll = async () => {
  return new Promise<void>((resolve) => {
    let totalHeight = 0;
    const distance = 100; // Scroll distance per step
    const timer = setInterval(() => {
      const scrollHeight = document.body.scrollHeight;
      window.scrollBy(0, distance);
      totalHeight += distance;

      // If we reached the bottom or scrolled enough
      if (window.scrollY + window.innerHeight >= scrollHeight || totalHeight >= scrollHeight) {
          clearInterval(timer);
          resolve();
      }
    }, 100); // Delay between scrolls
  });
};

export function extractRatingAndSales(str: string) {
  const soldIndex = str.indexOf('sold');
  if (soldIndex === -1) {
    return { rating: null, sales: null };
  }
  const beforeSold = str.substring(0, soldIndex).trim();
  const tokens = beforeSold.split(/\s+/).filter(t => t !== '');
  if (tokens.length === 0) {
    return { rating: null, sales: null };
  }
  const sales = tokens[tokens.length - 1];
  let rating = null;
  if (tokens.length >= 2) {
    const candidate = tokens[tokens.length - 2];
    const num = parseFloat(candidate);
    if (
      !isNaN(num) &&
      num >= 1 &&
      num <= 5 &&
      /^\d+(\.\d+)?$/.test(candidate)
    ) {
      rating = candidate;
    }
  }
  return { rating, sales };
}

export async function performSearch(keyword: string): Promise<boolean> {
  // 1. Find Search Input
  const searchInput = document.getElementById('search-words') || document.getElementById('search-wrods') as HTMLInputElement;
  
  if (searchInput && searchInput instanceof HTMLInputElement) {
    // 2. Input keywords
    if (!keyword) {
      alert('请输入搜索关键词');
      return false;
    }

    // Simulate human input
    searchInput.focus();
    searchInput.value = '';
    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
    
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
    if (nativeInputValueSetter) {
      nativeInputValueSetter.call(searchInput, keyword);
    } else {
      searchInput.value = keyword;
    }
    
    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
    searchInput.dispatchEvent(new Event('change', { bubbles: true }));
    searchInput.blur();
    
    // 3. Set automation flag
    localStorage.setItem('wm_automation_step', 'starting');
    
    // 4. Simulate Search Click
    const searchBtnSelectors = [
      '.search--submit--2VTbd-T', 
      '.search--newSubmit--3BlVRKw',
      'input.search-button',
      'button.search-button', 
      'input[type="submit"]', 
      'button[type="submit"]'
    ];
    
    let searchBtn: HTMLElement | null = null;
    
    for (const selector of searchBtnSelectors) {
      searchBtn = document.querySelector(selector) as HTMLElement;
      if (searchBtn) break;
    }
    
    if (!searchBtn && searchInput.parentElement) {
      searchBtn = searchInput.parentElement.querySelector('input[type="button"], button') as HTMLElement;
    }

    if (searchBtn) {
      console.log('Found search button:', searchBtn);
      searchBtn.click();
      return true;
    } else {
      console.log('Search button not found, falling back to form submit/enter');
      const form = searchInput.form;
      if (form) {
        form.submit();
        return true;
      } else {
        searchInput.dispatchEvent(new KeyboardEvent('keydown', { 
          key: 'Enter', 
          code: 'Enter', 
          keyCode: 13, 
          which: 13,
          bubbles: true 
        }));
        return true;
      }
    }
  } else {
    alert('未找到搜索框 (id=search-words)');
    return false;
  }
}

export async function parseProductList(): Promise<Product[]> {
  const cardList = document.getElementById('card-list');
  if (!cardList) {
    throw new Error('未找到商品列表 (id=card-list)');
  }
  
  const products: Product[] = [];
  Array.from(cardList.children).forEach((child) => {
    if (child.tagName !== 'DIV') return;
    
    const link = child.querySelector('a');
    if (!link) return;
    
    const firstDiv = link.children[0];
    const imgList: string[] = [];
    if (firstDiv) {
      firstDiv.querySelectorAll('img').forEach(img => {
        if (img.src) imgList.push(img.src);
      });
    }
    
    const secondDiv = link.children[1];
    let titleText = '';
    let spanText = '';
    let url = link.href;
    
    if (secondDiv) {
      Array.from(secondDiv.children).forEach((child) => {
        const h3List = child.querySelectorAll('h3');
        h3List.forEach((h3) => {
          const text = h3.textContent?.trim();
          if (text) {
            if (titleText) titleText += ' ';
            titleText += text;
          }
        });
        
        const spanList = child.querySelectorAll('span');
        spanList.forEach((span) => {
          const text = span.textContent?.trim();
          if (text) {
            if (spanText) spanText += ' ';
            spanText += text;
          }
        });
      });
    }

    let rating: string | null = null;
    let soldCount: string | null = null;
    if (spanText !== '') {
      const result = extractRatingAndSales(spanText);
      rating = result.rating;
      soldCount = result.sales;
    }

    const url_match = url.match(/\/item\/(\d+)\.html/);
    const itemId = url_match ? url_match[1] : "";
    
    products.push({
      id: itemId,
      images: imgList,
      title: titleText,
      info: spanText,
      url: url,
      rating: rating,
      soldCount: soldCount,
      reviewCount: '',
    });
  });
  
  return products;
}

export async function fetchProductDetails(item: Product): Promise<void> {
  if (!item.url) return;
  try {
    const newTab = window.open(item.url, '_blank');
    if (!newTab) {
      console.error('Failed to open tab for', item.url);
      return;
    }
    
    await new Promise<void>((resolve) => {
      let attempts = 0;
      const maxAttempts = 150; 
      const timer = setInterval(() => {
        attempts++;
        try {
          if (newTab.document.readyState === 'interactive' || newTab.document.readyState === 'complete') {
            const doc = newTab.document;
            const container = doc.querySelector('.reviewer--wrap--vGS7G6P') || doc.querySelector('[data-pl="product-reviewer"]');
            if (container) {
              const ratingEl = container.querySelector('.reviewer--rating--xrWWFzx strong') || container.querySelector('a[href*="nav-review"] strong');
              if (ratingEl) {
                item.rating = ratingEl.textContent?.trim() || null;
              }
              const reviewsEl = container.querySelector('.reviewer--reviews--cx7Zs_V');
              if (reviewsEl) {
                item.reviewCount = reviewsEl.textContent?.trim().replace('Reviews', '').trim() || '';
              }
              const soldEl = container.querySelector('.reviewer--sold--ytPeoEy');
              if (soldEl) {
                item.soldCount = soldEl.textContent?.trim().replace('sold', '').trim() || null;
              }
              clearInterval(timer);
              newTab.close();
              resolve();
              return;
            }
          }
        } catch (e) {
          // Ignore cross-origin issues
        }
        if (attempts >= maxAttempts) {
          console.warn('Timeout scraping:', item.url);
          clearInterval(timer);
          newTab.close();
          resolve();
        }
      }, 100);
    });
    await new Promise(r => setTimeout(r, 500));
  } catch (e) {
    console.error('Error scraping item:', item.url, e);
  }
}

export async function loginToIxSpy(username: string, password: string): Promise<boolean> {
  console.log('[IxSpy] Attempting login via background...');
  try {
    // @ts-ignore
    const runtime = (typeof browser !== 'undefined' ? browser : chrome).runtime;
    if (!runtime || !runtime.sendMessage) {
        console.error('[IxSpy] Runtime or sendMessage not available');
        return false;
    }

    const response = await new Promise<any>((resolve) => {
        runtime.sendMessage({
            type: 'IXSPY_LOGIN',
            payload: { username, password }
        }, (res: any) => {
            if (runtime.lastError) {
                console.error('[IxSpy] sendMessage error:', runtime.lastError);
                resolve({ success: false });
            } else {
                resolve(res);
            }
        });
    });
    
    console.log('[IxSpy] Login response:', response);
    return response && response.success;
  } catch (e) {
    console.error('IxSpy login failed', e);
    return false;
  }
}

export async function fetchIxSpyProductInfo(productId: string): Promise<{add_date: string} | null> {
  console.log('[IxSpy] Fetching info via background for:', productId);
  try {
    // @ts-ignore
    const runtime = (typeof browser !== 'undefined' ? browser : chrome).runtime;
    if (!runtime || !runtime.sendMessage) {
        console.error('[IxSpy] Runtime or sendMessage not available');
        return null;
    }

    const response = await new Promise<any>((resolve) => {
        runtime.sendMessage({
            type: 'IXSPY_FETCH_INFO',
            payload: { id: productId }
        }, (res: any) => {
            if (runtime.lastError) {
                console.error('[IxSpy] sendMessage error:', runtime.lastError);
                resolve({ success: false });
            } else {
                resolve(res);
            }
        });
    });
    
    if (response && response.success && response.data && response.data.add_date) {
        console.log('[IxSpy] Info received:', response.data);
        return { add_date: response.data.add_date };
    } else {
        if (response && response.error === 'Unauthorized') {
            console.warn('[IxSpy] Unauthorized');
            throw new Error('Unauthorized');
        }
    }
    return null;
  } catch (e: any) {
    if (e.message === 'Unauthorized') throw e;
    console.error('IxSpy fetch info failed', e);
    return null;
  }
}
