export function handleBaiduTask(message: any) {
  console.log(`[Baidu Service] Processing task: ${message.action}`);
  const { src, width, height } = message.payload;
  const return_obj = {
    status: 'success',
    processedAt: new Date().toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }),
    backgroundInfo: `Background analyzed ${width}x${height} image from Baidu`
  };
  console.log(`[Baidu Service] Returning result: ${JSON.stringify(return_obj)}`);
  return return_obj;
}
