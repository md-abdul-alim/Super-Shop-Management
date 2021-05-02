const searchField = document.querySelector('#searchField');
const searchTable = document.querySelector(".search-table");
searchTable.style.display = "none";
const mainTable = document.querySelector(".main-table");
const paginationContainer = document.querySelector(".pagination-container");
const noResults = document.querySelector(".no-result");
const searchTableBody = document.querySelector(".search-table-body");

searchField.addEventListener('keyup', (e)=>{
    const searchValue = e.target.value;
    //During search input how table/ pagination, no result will show and hide
    if(searchValue.trim().length>0){
        console.log("searchValue", searchValue);
        paginationContainer.style.display = "none";
        searchTableBody.innerHTML ="";

        //API Calling start from here
        fetch("/search-expenses/",{
            body: JSON.stringify({searchText: searchValue}),
            method: "POST",
        })
        .then(res=>res.json())
        .then(data=>{
            console.log("data", data)
            mainTable.style.display = "none";
            searchTable.style.display = "block";
            console.log("data.length",data.length);

            //if something found from search how the table show result
            if (data.length === 0){
                //searchTable.innerHTML = "No Result Found";
                searchTable.style.display = "none";
                noResults.style.display = "block";
            }else{
                noResults.style.display = "none";
                data.forEach(item=>{
                    searchTableBody.innerHTML +=`
                        <tr>
                            <td>${item.category}</td>
                            <td>${item.description}</td>
                            <td>${item.amount}</td>
                            <td>${item.date}</td>
                            <td><a href="/update-expense/${item.id}" class="btn btn-secondary btn-sm">Update</a></td>
                            <td><a href="/delete-expense/${item.id}" class="btn btn-danger btn-sm">Delete</a></td>
                        </tr>
                    `;
                });
            }
        });
    }else{
        mainTable.style.display = "block";
        paginationContainer.style.display = "block";
        searchTable.style.display = "none";
    }
})