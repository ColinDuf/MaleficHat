<template>
  <div class="members">
    <label for="rank">Rank:</label>
    <select id="rank" v-model="selectedRank" @change="fetchMembers">
      <option value="">All</option>
      <option v-for="rank in ranks" :key="rank" :value="rank">{{ rank }}</option>
    </select>

    <p v-if="count !== null">Total: {{ count }}</p>

    <ul>
      <li v-for="member in members" :key="member.id">{{ member.name }} ({{ member.rank }})</li>
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
  const response = await fetch(`/api/members${params}`);
  const data = await response.json();
  members.value = data.members;
  count.value = data.count;
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