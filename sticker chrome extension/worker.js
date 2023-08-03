chrome.runtime.onInstalled.addListener(function () {
	chrome.contextMenus.create({
		title: "Add as sticker",
	    contexts: ["image"],
	    id: "EmoteMenu"
	});
});

chrome.contextMenus.onClicked.addListener(function (info) {
	let image = info.srcUrl
	console.log(image);
	chrome.storage.local.set({ "currentImage": image }).then(() => {
		console.log("Value was set");
	});
});