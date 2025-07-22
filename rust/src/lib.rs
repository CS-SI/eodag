use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyAsyncIterator};
use pyo3_asyncio::tokio::future_into_py;
use aws_sdk_s3::{Client, Region};
use aws_config::meta::region::RegionProviderChain;
use bytes::Bytes;
use tokio_stream::{Stream, StreamExt};
use anyhow::Result;
use std::pin::Pin;

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

// Shared Tokio runtime is auto-initialized by pyo3 with "auto-initialize" feature

async fn fetch_range_streaming(
    client: &Client,
    bucket: &str,
    key: &str,
    start: usize,
    end: usize,
    sub_chunk_size: usize,
) -> Result<impl Stream<Item = Result<Bytes>>> {
    let range_header = format!("bytes={}-{}", start, end);
    let resp = client
        .get_object()
        .bucket(bucket)
        .key(key)
        .range(range_header)
        .send()
        .await?;

    let stream = resp.body;
    let mut reader = StreamReader::new(stream.map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e)));

    let stream = try_stream! {
        let mut buf = vec![0u8; sub_chunk_size];
        loop {
            let n = reader.read(&mut buf).await?;
            if n == 0 {
                break;
            }
            yield Bytes::copy_from_slice(&buf[..n]);
         }
    };

    Ok(stream)
}

/// Compute byte ranges to download from a file, considering a global byte range and chunk size.
/// `byte_range` = (Option<start>, Option<end>) in global logical stream coordinates.
fn compute_file_ranges(
    file_info: &FileInfo,
    byte_range: (Option<usize>, Option<usize>),
    range_size: usize,
) -> Option<Vec<(usize, usize)>> {
    let file_size = file_info.size;
    let file_start_offset = file_info.file_start_offset;
    let file_end_offset = file_start_offset + file_size - 1;

    let (range_start_opt, range_end_opt) = byte_range;

    // Check for no overlap
    if let (Some(range_start), Some(range_end)) = (range_start_opt, range_end_opt) {
        if file_end_offset < range_start || file_start_offset > range_end {
            return None; // no overlap, skip this file
        }
    }

    // Calculate adjusted start/end inside the file
    let mut start = 0usize;
    let mut end = file_size - 1;

    if let Some(range_start) = range_start_opt {
        start = start.max(range_start.saturating_sub(file_start_offset));
    }
    if let Some(range_end) = range_end_opt {
        end = end.min(range_end.saturating_sub(file_start_offset));
    }

    // Adjust for data offset inside file
    start += file_info.data_start_offset;
    end += file_info.data_start_offset;

    // Split into chunk ranges
    let mut ranges = Vec::new();
    let mut chunk_start = start;

    while chunk_start <= end {
        let chunk_end = usize::min(chunk_start + range_size - 1, end);
        ranges.push((chunk_start, chunk_end));
        chunk_start += range_size;
    }

    Some(ranges)
}

/// Stream bytes chunk by chunk for multiple files
async fn stream_files(
    files: Vec<FileInfo>,
    range_size: usize,
    region: String,
) -> Result<impl Stream<Item = Result<Bytes>>> {
    // Configure AWS region (use default chain, fallback to provided region)
    let region_provider = RegionProviderChain::default_provider().or_else(Region::new(region));
    let config = aws_config::from_env().region(region_provider).load().await;
    let client = Client::new(&config);

    // Create a stream that yields chunks one by one for all files sequentially
    let stream = tokio_stream::iter(files)
        .flat_map(move |file| {
            let client = client.clone();
            let bucket = file.bucket_name.;
            let key = file.key.;
            let size = file.size;
            let range_size = range_size;

            // Stream over chunks for this file
            let file_stream = async_stream::try_stream! {
                let mut pos = 0usize;
                while pos < size {
                    let end = usize::min(pos + range_size - 1, size - 1);
                    let chunk = fetch_range(&client, &bucket, &key, pos, end).await?;
                    yield chunk;
                    pos += range_size;
                }
            };
            file_stream
        });
    Ok(stream)
}

#[pyfunction]
fn stream_download_from_s3_py(
    py: Python,
    files: Vec<FileInfo>,
    range_size: usize,
    region: String,
) -> PyResult<PyObject> {
    // Convert Rust Stream into Python async generator using pyo3-asyncio
    future_into_py(py, async move {
        let stream = stream_files(files, range_size, region).await?;
        // Convert each bytes chunk to Python bytes
        let py_stream = stream.map(|res| res.map(|chunk| chunk.to_vec()));
        Ok::<_, anyhow::Error>(py_stream)
    })
}

#[pymodule]
fn s3_streamer(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<FileInfo>()?;
    m.add_function(wrap_pyfunction!(stream_download_from_s3_py, m)?)?;
    Ok(())
}
