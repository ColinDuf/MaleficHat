<template>
  <div class="members">
    <label for="rank">Rank:</label>
    <select id="rank" v-model="selectedRank" @change="fetchMembers">
      <option value="">All</option>
      <option v-for="rank in ranks" :key="rank" :value="rank">{{ rank }}</option>
    </select>

    <p v-if="count !== null">Total: {{ count }}</p>

    <ul>
      <li v-for="member in members" :key="member.username">
        {{ member.username }} - {{ member.rank }} {{ member.tier || '' }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const ranks = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Master', 'Grandmaster', 'Challenger'];
const selectedRank = ref('');
const members = ref([]);
const count = ref(null);

async function fetchMembers() {
  const params = selectedRank.value ? `?rank=${encodeURIComponent(selectedRank.value)}` : '';
  try {
    const response = await fetch(`/api/members${params}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    members.value = data.members;
    count.value = data.count;
  } catch (err) {
    console.error('Failed to fetch members', err);
    members.value = [];
    count.value = null;
  }
}

// Fetch all members on component mount
fetchMembers();
</script>

<style scoped>
.members {
  max-width: 600px;
  margin: 2rem auto;
  font-family: sans-serif;
}

select {
  margin-bottom: 1rem;
}

ul {
  list-style: none;
  padding: 0;
}
</style>