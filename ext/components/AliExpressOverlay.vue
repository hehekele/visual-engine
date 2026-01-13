<template>
  <div class="aliexpress-overlay">
    <!-- Floating Layer -->
    <div v-if="showFloatingLayer" class="floating-layer">
      <input 
        v-model="keyword" 
        placeholder="输入关键词..." 
        class="search-input"
      />
      <input 
        v-model.number="targetCount" 
        type="number" 
        class="count-input"
        placeholder="数量"
        min="1"
        title="目标采集数量"
        style="width: 60px"
      />
      <button 
        @click="showIxSpyLogin = !showIxSpyLogin" 
        class="icon-btn"
        title="设置 IxSpy 账号"
      >
        ⚙️
      </button>
      <button 
        @click="handleSearch" 
        :disabled="isProcessing"
        class="action-btn"
        :style="{ opacity: isProcessing ? 0.7 : 1, cursor: isProcessing ? 'wait' : 'pointer' }"
      >
        {{ btnText }}
      </button>
    </div>
    
    <!-- IxSpy Login Modal/Popup -->
    <div v-if="showIxSpyLogin" class="settings-panel">
      <h3>IxSpy 设置</h3>
      <div class="input-group">
        <label>用户名:</label>
        <input v-model="ixSpyUser" placeholder="Email" />
      </div>
      <div class="input-group">
        <label>密码:</label>
        <input v-model="ixSpyPass" type="password" placeholder="Password" />
      </div>
      <div class="btn-row">
        <button @click="showIxSpyLogin = false" class="small-btn">关闭</button>
      </div>
    </div>

    <!-- Result Modal -->
    <div v-if="showModal" class="modal-overlay">
      <div class="modal-content">
        <div class="info-list">
          <div class="info-row" v-for="(value, label) in summaryInfo" :key="label">
             <span class="label">{{ label }}: </span>
             <span class="value">{{ value }}</span>
          </div>
          
          <div class="product-list">
            <div v-for="(item, index) in products" :key="index" class="product-item">
              <div class="product-title">
                <strong>#{{ index + 1 }}</strong><br/>
                <span>商品名称：{{ item.title || '无标题' }}</span><br/>
                <span>累计销量：{{ item.soldCount || '无销量' }}</span><br/>
                <span>评论数量：{{ item.reviewCount || '无评论数' }}</span><br/>
                <span>商品评分：{{ item.rating || '无评分' }}</span><br/>
                <span>上架时间：{{ item.add_date || '未知' }}</span><br/>
                <span>商品代码：{{ item.id || '无商品ID' }}</span><br/>
                <span>商品链接：<a :href="item.url || '#'" target="_blank">{{ item.url || '无链接' }}</a></span>
              </div>
              <div v-if="item.images && item.images.length" class="img-container">
                <img v-for="img in item.images" :src="img" :key="img" class="product-img" />
              </div>
            </div>
          </div>
          
        </div>
        
        <div class="btn-container">
          <button @click="closeModal" class="close-btn">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { 
  performSearch, 
  autoScroll, 
  parseProductList, 
  fetchProductDetails,
  fetchIxSpyProductInfo,
  loginToIxSpy,
  type Product 
} from '@/utils/aliexpress/aliexpress';

const keyword = ref('');
const targetCount = ref();
const ixSpyUser = ref('');
const ixSpyPass = ref('');
const showIxSpyLogin = ref(false);
const isProcessing = ref(false);
const btnText = ref('搜索并采集');
const showFloatingLayer = ref(true);
const showModal = ref(false);
const products = ref<Product[]>([]);
const summaryInfo = ref<Record<string, any>>({});

// Check if we should show the floating layer (not on item page)
const isItemPage = window.location.pathname.includes('/item/');
showFloatingLayer.value = !isItemPage;

const handleSearch = async () => {
  if (isProcessing.value) return;
  if (!keyword.value) {
    alert('请输入关键词！');
    return;
  }
  if (!targetCount.value) {
    alert('请输入目标采集数量！');
    return;
  }
  
  // Start new search: clear collected products
  localStorage.removeItem('wm_collected_products');
  localStorage.setItem('wm_target_count', targetCount.value.toString());
  
  // If we are just starting search
  const success = await performSearch(keyword.value);
  if (success) {
      btnText.value = '正在搜索...';
  }
};

const startScraping = async () => {
  isProcessing.value = true;
  
  // Load previously collected products
  let collectedProducts: Product[] = [];
  try {
    const stored = localStorage.getItem('wm_collected_products');
    if (stored) {
      collectedProducts = JSON.parse(stored);
    }
    const storedCount = localStorage.getItem('wm_target_count');
    if (storedCount) {
        targetCount.value = parseInt(storedCount);
    }
  } catch (e) {
    console.error('Error parsing collected products:', e);
  }
  
  if (!targetCount.value) {
      // If targetCount is lost, try to prompt or default? 
      // Ideally this shouldn't happen if we save it in handleSearch
      // But if user manually refreshes, it might be persisted.
      // Let's just log warning.
      console.warn('Target count not found, defaulting to infinite? Or stopping?');
  }

  btnText.value = collectedProducts.length > 0 
    ? `已采集${collectedProducts.length}个，正在滚动加载...` 
    : '正在滚动加载...';
  
  // Helper function to handle pagination
  const tryNextPage = async (currentList: Product[]) => {
    // Try multiple strategies to find the next button
    let nextBtn: HTMLElement | null = null;
    
    // Strategy 1: Existing specific selector (Comet UI)
    // Note: The arrow icon class might vary, so we look for the button class and maybe position
    const paginationBtns = Array.from(document.querySelectorAll('button.comet-pagination-item-link'));
    if (paginationBtns.length > 0) {
        // Usually the last button is 'Next', or the one with specific icon
        // Check for the icon
        nextBtn = paginationBtns.find(btn => btn.querySelector('.comet-icon-arrowleftrtl32')) as HTMLElement;
        
        // If not found by icon, assume the last pagination button is Next if it's not a number
        if (!nextBtn) {
            const lastBtn = paginationBtns[paginationBtns.length - 1];
            // Check if it's a number
            if (isNaN(parseInt(lastBtn.textContent || ''))) {
                 nextBtn = lastBtn as HTMLElement;
            }
        }
    }

    // Strategy 2: Look for generic 'Next' text or standard classes
    if (!nextBtn) {
        const candidates = Array.from(document.querySelectorAll('button, a.next, li.next a'));
        nextBtn = candidates.find(el => {
            const text = el.textContent?.trim().toLowerCase();
            const ariaLabel = el.getAttribute('aria-label')?.toLowerCase();
            return (
                text === 'next' || 
                text === 'next page' || 
                text === '下一页' || 
                ariaLabel === 'next page' ||
                ariaLabel === 'next'
            );
        }) as HTMLElement;
    }

    // Strategy 3: Look for 'next' in class name inside pagination container
    if (!nextBtn) {
         const pagination = document.querySelector('.pagination, .comet-pagination');
         if (pagination) {
             nextBtn = pagination.querySelector('.next, .next-page, [class*="next"]') as HTMLElement;
         }
    }
    
    if (nextBtn && !nextBtn.hasAttribute('disabled') && !nextBtn.classList.contains('disabled')) {
      btnText.value = `已找到${currentList.length}个满足条件商品(目标${targetCount.value}个)，正在翻页...`;
      
      // Save current progress
      localStorage.setItem('wm_collected_products', JSON.stringify(currentList));
      localStorage.setItem('wm_target_count', targetCount.value.toString());
      localStorage.setItem('wm_automation_step', 'starting');
      
      nextBtn.click();
      
      // Wait to determine if page reloads or SPA update
      await new Promise(r => setTimeout(r, 5000));
      
      if (localStorage.getItem('wm_automation_step') === 'starting') {
        // SPA: Page didn't reload, remove flag and recurse
        localStorage.removeItem('wm_automation_step');
        await startScraping();
      }
      return true;
    }
    return false;
  };
  
  await autoScroll();
  
  btnText.value = '正在采集数据...';
  await new Promise(r => setTimeout(r, 1000));
  
  try {
    const rawProducts = await parseProductList();
    
    // Filter and Process
    let data = rawProducts.filter(item => !item.info?.includes('Dollar Express'));
    data = data.filter(item => item.soldCount !== '' && parseInt(item.soldCount || '0') >= 200);
    data = data.filter(item => item.rating !== '' && parseFloat(item.rating || '0') >= 4.0);
    
    // IxSpy Filtering (Add Date < 60 days check)
    if (data.length > 0) {
        btnText.value = '正在检查上架时间...';
        const finalData: Product[] = [];
        
        for (const item of data) {
           let info = await fetchIxSpyProductInfo(item.id);
           
           if (!info && ixSpyUser.value && ixSpyPass.value) {
              // Try login if info fetch failed (likely 401) and we have creds
              // We could optimize to only login once, but for simplicity:
              const loggedIn = await loginToIxSpy(ixSpyUser.value, ixSpyPass.value);
              if (loggedIn) {
                 info = await fetchIxSpyProductInfo(item.id);
              }
           }
           
           if (info && info.add_date) {
              item.add_date = info.add_date;
              const addDate = new Date(info.add_date);
              const now = new Date();
              const diffTime = Math.abs(now.getTime() - addDate.getTime());
              const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
              
              // Filter out if less than 60 days
              if (diffDays >= 60) {
                 finalData.push(item);
              }
           } else {
              // Keep if we can't determine date (or change policy if needed)
              finalData.push(item);
           }
           // Small delay to be nice
           await new Promise(r => setTimeout(r, 500));
        }
        data = finalData;
    }

    // Fetch details for each（打开商品详情页，主要为了获取评论数量）
    if (data.length > 0) {
        for (const item of data) {
            await fetchProductDetails(item);
        }
        // 过滤掉评论数量超过销量1/3的商品
        data = data.filter(item => item.reviewCount !== '' && parseInt(item.reviewCount || '0') < parseInt(item.soldCount || '0') / 3);
    }
    
    const totalProducts = [...collectedProducts, ...data];

    // 如果总数量不足 targetCount，尝试翻页
    if (totalProducts.length < targetCount.value) {
      if (await tryNextPage(totalProducts)) return;
    }

    products.value = totalProducts;
    localStorage.removeItem('wm_collected_products');
    localStorage.removeItem('wm_target_count');
    
    summaryInfo.value = {
        '采集到的数量': totalProducts.length,
        '条件1': '过滤掉 Dollar Express 专题页',
        '条件2': '累计销售 >= 200',
        '条件3': '评分 >= 4.0',
        '条件4': '上架时间 >= 60天',
        '条件5': '评论数量低于销量的1/3',
    };
    
    showModal.value = true;
    
  } catch (e: any) {
    alert(e.message || 'Error scraping');
  } finally {
    isProcessing.value = false;
    btnText.value = '搜索并采集';
  }
};

const closeModal = () => {
  showModal.value = false;
};

watch(ixSpyUser, (val) => {
  localStorage.setItem('wm_ixspy_user', val);
});

watch(ixSpyPass, (val) => {
  localStorage.setItem('wm_ixspy_pass', val);
});

onMounted(() => {
  const savedUser = localStorage.getItem('wm_ixspy_user');
  if (savedUser) ixSpyUser.value = savedUser;
  
  const savedPass = localStorage.getItem('wm_ixspy_pass');
  if (savedPass) ixSpyPass.value = savedPass;

  const automationStep = localStorage.getItem('wm_automation_step');
  if (automationStep === 'starting') {
    localStorage.removeItem('wm_automation_step');
    setTimeout(() => {
       startScraping();
    }, 1000);
  }
});
</script>

<style scoped>
.floating-layer {
  position: fixed;
  top: 100px;
  right: 60px;
  padding: 10px;
  border-radius: 10px;
  background-color: #4e54c8;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2147483647;
  box-shadow: 0 4px 15px rgba(0,0,0,0.3);
  font-family: Arial, sans-serif;
  font-weight: bold;
  font-size: 12px;
  gap: 8px;
  user-select: none;
  pointer-events: auto;
}

.search-input {
  padding: 5px 8px;
  border-radius: 4px;
  border: none;
  width: 120px;
  font-size: 12px;
  color: #333;
  outline: none;
}

.count-input {
  padding: 5px 8px;
  border-radius: 4px;
  border: none;
  width: 50px;
  font-size: 12px;
  color: #333;
  outline: none;
}

.action-btn {
  padding: 6px 12px;
  background-color: white;
  color: #4e54c8;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0,0,0,0.5);
  z-index: 2147483647;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  background-color: white;
  padding: 25px;
  border-radius: 12px;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 10px 25px rgba(0,0,0,0.2);
  font-family: Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  color: #333;
}

.info-row {
  margin-bottom: 12px;
  display: flex;
  align-items: flex-start;
  font-size: 14px;
}

.label {
  font-weight: bold;
  width: 100px;
  flex-shrink: 0;
}

.value {
  word-break: break-all;
  color: #555;
  flex: 1;
}

.product-list {
  margin: 10px 0;
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #eee;
  padding: 10px;
}

.product-item {
  border-bottom: 1px solid #eee;
  padding: 10px 0;
}

.product-title span {
  color: #333;
  font-size: 0.9em;
}

.product-title a {
  color: #4e54c8;
}

.img-container {
  display: flex;
  gap: 5px;
  overflow-x: auto;
  padding-bottom: 5px;
  margin-top: 5px;
}

.product-img {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.btn-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.close-btn {
  padding: 8px 20px;
  background-color: #4e54c8;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
  font-size: 14px;
}

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  padding: 0 5px;
}

.settings-panel {
  position: absolute;
  top: 50px;
  right: 0;
  background: white;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.2);
  color: #333;
  width: 250px;
  z-index: 2147483648;
}

.settings-panel h3 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #4e54c8;
}

.input-group {
  margin-bottom: 10px;
}

.input-group label {
  display: block;
  font-size: 12px;
  margin-bottom: 4px;
}

.input-group input {
  width: 100%;
  padding: 5px;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-sizing: border-box; /* Important for width 100% */
}

.btn-row {
  display: flex;
  justify-content: flex-end;
}

.small-btn {
  padding: 4px 10px;
  background-color: #eee;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
</style>
