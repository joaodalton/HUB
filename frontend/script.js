async function buscar() {
  const termo = document.getElementById('busca').value;
  const resposta = await fetch(`http://localhost:8000/search?q=${encodeURIComponent(termo)}`);
  const dados = await resposta.json();

  const lista = document.getElementById('resultados');
  lista.innerHTML = '';

  if (dados.length === 0) {
    lista.innerHTML = '<li>Nenhum resultado encontrado.</li>';
    return;
  }

  dados.forEach(item => {
    const tipo = item.mimeType.includes('folder') ? '📁' : '📄';
    lista.innerHTML += `
      <li>${tipo} <a href="${item.webViewLink}" target="_blank">${item.name}</a></li>
    `;
  });
}