let cropper;

const photoUpload = document.getElementById('photoUpload');
const imageToCrop = document.getElementById('imageToCrop');
const cropperModal = document.getElementById('cropperModal');
const cropBtn = document.getElementById('cropBtn');
const cancelCrop = document.getElementById('cancelCrop');

photoUpload.addEventListener('change', function (e) {
  const file = e.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = function (event) {
      imageToCrop.src = event.target.result;

      cropperModal.style.display = 'flex';
      document.body.style.overflow = 'hidden';

      cropper = new Cropper(imageToCrop, {
        aspectRatio: 1,
        viewMode: 1,
        autoCropArea: 1,
        responsive: true,
      });
    };
    reader.readAsDataURL(file);
  }
});

cropBtn.addEventListener('click', function () {
  if (!cropper) return;

  const canvas = cropper.getCroppedCanvas({
    width: 300,
    height: 300,
  });

  canvas.toBlob(function (blob) {
    const formData = new FormData();
    formData.append('cropped_image', blob);

    fetch(uploadUrl, {
      method: 'POST',
      headers: {
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
      },
      body: formData
    }).then(response => {
      if (response.ok) {
        location.reload();
      } else {
        alert('Failed to upload photo.');
      }
    });
  });

  cropper.destroy();
  cropper = null;
  cropperModal.style.display = 'none';
  document.body.style.overflow = '';
});

cancelCrop.addEventListener('click', function () {
  if (cropper) {
    cropper.destroy();
    cropper = null;
  }
  cropperModal.style.display = 'none';
  document.body.style.overflow = '';
});



