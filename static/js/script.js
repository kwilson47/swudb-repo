document.addEventListener('DOMContentLoaded', function () {
  // const cardImages = document.querySelectorAll('.card-image');
  var toggleableCards = document.querySelectorAll('.toggleable');
  toggleableCards.forEach(function (cardImage) {
    cardImage.addEventListener('click', function () {
      const backImage = cardImage.getAttribute('data-back-image');
      const currentSrc = cardImage.getAttribute('src');

      if (currentSrc === backImage) {
        // Display front side
        cardImage.setAttribute('src', cardImage.getAttribute('data-front-image'));
      } else {
        // Display back side
        cardImage.setAttribute('src', backImage);
      }
    });
  });
});




function buildUpdatedURL(sortField, sortOrder, selectedDisplayMode) {
  const currentURL = window.location.href;
  let updatedURL;

  // Check if the URL already contains the 'sort' parameter
  if (currentURL.includes('&sort=')) {
    updatedURL = currentURL.replace(/(&|\?)sort=[^&]+/, '$1sort=' + sortField);
  } else {
    // Append the 'sort' parameter to the URL
    updatedURL = currentURL + (currentURL.includes('?') ? '&' : '?') + 'sort=' + sortField;
  }

  // Check if the URL already contains the 'sort' parameter
  if (updatedURL.includes('&sortOrder=')) {
    updatedURL = updatedURL.replace(/(&|\?)sortOrder=[^&]+/, '$1sortOrder=' + sortOrder);
  } else {
    // Append the 'sort' parameter to the URL
    updatedURL = updatedURL + (updatedURL.includes('?') ? '&' : '?') + 'sortOrder=' + sortOrder;
  }


  return updatedURL;
}

// Attach event listener to all toggle buttons
const toggleButtons = document.querySelectorAll('.toggle-button');
toggleButtons.forEach(button => {
  button.addEventListener('click', () => {
    // Find the image element within the button's parent container
    const image = button.parentNode.querySelector('.card-image');
    // Toggle the image by changing its source or visibility
    // Implement your specific logic here
    const backImage = image.getAttribute('data-back-image');
    const currentSrc = image.getAttribute('src');

    if (currentSrc === backImage) {
      // Display front side
      image.setAttribute('src', image.getAttribute('data-front-image'));
    } else {
      // Display back side
      image.setAttribute('src', backImage);
    }
  });
});