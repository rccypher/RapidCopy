# Frequently Asked Questions (FAQ)

## General

### How do I restart SeedSync Debian Service?

SeedSync can be restarted from the web GUI. If that fails, you can restart the service from command-line:

    :::bash
    sudo service seedsync restart


### How can I save my settings across updates when using the Docker image?

To maintain state across updates, you can store the settings in the host machine.
Add the following option when starting the container.

    :::bash
    -v <directory on host>:/config

where `<directory on host>` refers to the location on host machine where you wish to store the application
state.


### How do I sync files from multiple remote directories?

Use **Path Mappings** in the Settings page. Each path mapping pairs a remote directory with a local
directory. You can add as many mappings as needed. See the [Usage](usage.md#path-mappings) page for details.

### How do I verify my downloads are not corrupted?

Enable **Download Validation** in the Settings page. SeedSync will compute SHA256 checksums on both
the remote and local files after each download and automatically re-download any files that don't match.
For large files, you can enable chunked validation to only re-download the corrupted portions.
See the [Usage](usage.md#download-validation) page for details.


## Security

### Does SeedSync collect any data?

No, SeedSync does not collect any data.


## Troubleshooting

### SeedSync can't seem to connect to my remote server?

Make sure your remote server address was entered correctly.
If using password-based login, make sure the password is correct.
Check the logs for details about the exact failure.

### I am getting some errors about locale?

On some servers you may see errors in the log like so:
`Unpickling error: unpickling stack underflow b'bash: warning: setlocale: LC_ALL: cannot change locale`

This means your remote server requires that the locale matches with the Seedsync app.
We can fix this my changing the locale for Seedsync.
For Seedsync docker, try adding the following options to the `docker run` command:
```
-e LC_ALL=en_US.UTF-8
-e LANG=en_US.UTF-8
```

See [this issue](https://github.com/ipsingh06/seedsync/issues/66) for more details.
