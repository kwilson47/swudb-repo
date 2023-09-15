document.addEventListener('DOMContentLoaded', function() {
    var statsContainer = document.getElementById('stats-container');
    var statRow = statsContainer.querySelector('.stat-row');
    var valueInput = statRow.querySelector('.value-input');
    var counter = 1;

    valueInput.addEventListener('input', function() {
        var inputValue = valueInput.value.trim();
        if (inputValue !== '' && counter < 3 && !isExistingBlankValueInput()) {
            var newStatRow = createStatRow(counter);
            statsContainer.appendChild(newStatRow);
            counter++;

            // Attach event listener to the new value input
            var newValueInput = newStatRow.querySelector('.value-input');
            newValueInput.addEventListener('input', valueInputHandler);
        }
    });

    function createStatRow(index) {
        var row = document.createElement('div');
        row.className = 'stat-row';

        var statSelect = document.createElement('select');
        statSelect.className = 'stat-select select-dropdown select-dropdown-stats';
        statSelect.name = 'stat-select-' + (index + 1);
        statSelect.innerHTML = `
            <option value="c">Cost</option>
            <option value="p">Power</option>
            <option value="h">HP</option>
        `;
        row.appendChild(statSelect);

        var operatorSelect = document.createElement('select');
        operatorSelect.className = 'operator-select select-dropdown select-dropdown-stats';
        operatorSelect.name = 'operator-select-' + (index + 1);
        operatorSelect.innerHTML = `
            <option value="=">equal to</option>
            <option value="<">less than</option>
            <option value=">">greater than</option>
            <option value="<=">less than or equal to</option>
            <option value=">=">greater than or equal to</option>
            <option value="!=">not equal to</option>
        `;
        row.appendChild(operatorSelect);

        var valueInput = document.createElement('input');
        valueInput.type = 'text';
        valueInput.className = 'value-input search-box-stats';
        valueInput.name = 'value-input-' + (index + 1);
        row.appendChild(valueInput);

        return row;
    }

    function isExistingBlankValueInput() {
        var valueInputs = statsContainer.querySelectorAll('.value-input');
        for (var i = 0; i < valueInputs.length; i++) {
            if (valueInputs[i].value.trim() === '') {
                return true;
            }
        }
        return false;
    }

    function valueInputHandler() {
        var inputValue = this.value.trim();
        if (inputValue !== '' && counter < 3 && !isExistingBlankValueInput()) {
            var newStatRow = createStatRow(counter);
            statsContainer.appendChild(newStatRow);
            counter++;

            // Attach event listener to the new value input
            var newValueInput = newStatRow.querySelector('.value-input');
            newValueInput.addEventListener('input', valueInputHandler);
        }
    }

    // Attach event listener to the initial value input
    valueInput.addEventListener('input', valueInputHandler);
});



$(document).ready(function() {
  // Get a reference to the form
  var searchForm = $('#adv-search-form');

  // Add submit event listener to the form
  searchForm.submit(validateSelections);

  // Validation function
  function validateSelections(event) {
    var leaderValue = $('#leader-select').val();
    var baseValue = $('#base-select').val();

    // Check if either leader or base is selected
    if (leaderValue || baseValue) {
      // Ensure that both leader and base are selected
      if (!leaderValue || !baseValue) {
        // Display an error message or perform any desired actions
        alert('Please select both a leader and a base.');

        // Prevent the form submission
        event.preventDefault();
      }
    }
  }
});

  