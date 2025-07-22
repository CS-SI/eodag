use pyo3::prelude::*;
use aws_sdk_s3::{Client, Region};
use aws_sdk_s3::primitives::ByteStream;
use tokio::runtime::Runtime;
use std::cmp::min;

#[pyclass]
#[derive(Clone)]
pub struct FileInfo {
    #[pyo3(get, set)]
    pub size: usize,
    #[pyo3(get, set)]
    pub key: String,
    #[pyo3(get, set)]
    pub bucket_name: String,
    #[pyo3(get, set)]
    pub zip_filepath: Option<String>,
}

#[pyfunction]
pub fn stream_download_from_s3_py(
    py: Python,
    files: Vec<FileInfo>,
    range_size: usize,
    region: String,
) -> PyResult<PyObject> {
    let rt = Runtime::new().unwrap();
    let output_stream = py.allow_threads(move || {
        rt.block_on(stream_files(files, range_size, region))
    })?;

    // Convert Vec<Vec<u8>> to Python list of bytes
    let py_list = PyList::new(py, output_stream.into_iter().map(|chunk| PyBytes::new(py, &chunk)));
    Ok(py_list.into_py(py))
}

async fn fetch_range(
    client: &Client,
    bucket: &str,
    key: &str,
    start: usize,
    end: usize,
) -> anyhow::Result<bytes::Bytes> {
    let range_header = format!("bytes={}-{}", start, end);
    let resp = client
        .get_object()
        .bucket(bucket)
        .key(key)
        .range(range_header)
        .send()
        .await?;

    let data = resp.body.collect().await?.into_bytes();
    Ok(data)
}

async fn stream_files(
    files: Vec<FileInfo>,
    range_size: usize,
    region: String,
) -> anyhow::Result<Vec<Vec<u8>>> {
    let config = aws_config::from_env().region(Region::new(region)).load().await;
    let client = Client::new(&config);

    let mut output = vec![];
    for file in files.iter() {
        let size = file.size;
        let mut pos = 0;
        while pos < size {
            let end = min(pos + range_size - 1, size - 1);
            let chunk = fetch_range(&client, &file.bucket_name, &file.key, pos, end).await?;
            output.push(chunk.to_vec());
            pos += range_size;
        }
    }

    Ok(output)
}
