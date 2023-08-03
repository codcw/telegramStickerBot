let img = document.createElement('img');
chrome.storage.local.get(["currentImage"]).then((result) => {
  let pic = result.currentImage
  console.log("Value currently is " + pic);
  img.src = pic;
});
document.getElementById('pic').appendChild(img);
console.log("Image Element Added.");

async function fetchData() {
  try {
    const res = await fetch("http://localhost:5000/getPacks");
    const stickerset = await res.json();
    Object.entries(stickerset).forEach(([key, value]) => {
      let option = document.createElement('option');
      option.value = value;
      option.innerHTML = key;
      document.getElementById('packselect').appendChild(option);
    });
  }
  catch (error) {
    if (error instanceof TypeError) {
      let nobot = document.createElement('p');
      nobot.innerHTML = "Bot isn't online"
      document.getElementById('container').appendChild(nobot);
      console.log('failed to fetch', error);
    } else {
      console.log('other error', error);
    }
  }
}

fetchData();

document.getElementById("packbutton").addEventListener("click", add);

function add() {
  var e = document.getElementById("packselect");
  var packtitle = e.options[e.selectedIndex].value;
  var packname = e.options[e.selectedIndex].text;
  var emojifield = document.querySelector('.emojifield');
  var emojis = emojifield.textContent;
  fetch("http://localhost:5000/updateFromExtension", {
    method: "POST",
    body: JSON.stringify({
      packname: packname,
      packtitle: packtitle,
      pic: img.src,
      emojis: emojis
    }),
    headers: {
      "Content-type": "application/json; charset=UTF-8"
    }
  });
};