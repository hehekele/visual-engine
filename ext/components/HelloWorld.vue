<script lang="ts" setup>
import { ref } from 'vue';

defineProps({
  msg: String,
});

const count = ref(0);
</script>

<template>
  <h1>{{ msg }}</h1>
  <div>
    <!-- <button type="button" @click="count++">count is {{ count }}</button> -->
    <p>
      Powered by <a href="https://www.wmdigit.ai/" target="_blank">WMDIGIT</a>
    </p>
  </div>
</template>

<style scoped>
.read-the-docs {
  color: #888;
}
</style>
